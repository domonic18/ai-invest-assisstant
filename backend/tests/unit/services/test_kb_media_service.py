"""知识库素材接入服务单测：建行/预签名、上传核对、去重、软删与恢复。"""

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.constants.kb import KbProcessStatus
from app.core.clock import utc_now
from app.core.database import Base
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.account_quota import AdminAuditLog
from app.models.kb import KbKnowledgePoint, KbMedia, KbSource, KbTranscriptSegment
from app.schemas.kb import (
    KbMediaInitItem,
    KbMediaInitRequest,
    KbMediaPatchRequest,
    KbSourceCreateRequest,
    KbSourceUpdateRequest,
    KbUploadSessionRequest,
)
from app.services.common.minio_service import MultipartPart
from app.services.kb import media_service, source_service

pytestmark = pytest.mark.unit


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                KbSource.__table__,
                KbMedia.__table__,
                KbTranscriptSegment.__table__,
                KbKnowledgePoint.__table__,
                AdminAuditLog.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


def _patch_lock(acquired: bool = True):
    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield acquired

    return patch(
        "app.services.kb.source_service.redis_lock",
        side_effect=fake_lock,
    )


def _patch_minio(
    *,
    stat: tuple[int, str] | None = None,
) -> tuple[Any, MagicMock]:
    minio = MagicMock()
    minio.presigned_put_url = AsyncMock(return_value="https://cos/put")
    minio.stat_object = AsyncMock(return_value=stat)
    minio.remove_files = AsyncMock(return_value=None)
    cm = patch(
        "app.services.kb.media_service.get_minio_service", return_value=minio
    )
    return cm, minio


def _init_item(
    file_name: str = "L01.mp4",
    *,
    hash_: str = "a" * 32,
    media_kind: str = "video",
    episode_no: int | None = None,
) -> KbMediaInitItem:
    return KbMediaInitItem(
        fileName=file_name,
        relativePath=file_name,
        size=100,
        hash=hash_,
        mediaKind=media_kind,
        episodeNo=episode_no,
        durationSeconds=60,
    )


async def _seed_media(
    session: AsyncSession,
    source_id: int,
    *,
    episode_no: int | None = 1,
    hash_: str = "b" * 32,
    file_size: int = 500,
    deleted: bool = False,
) -> KbMedia:
    row = KbMedia(
        source_id=source_id,
        media_kind="course",
        episode_no=episode_no,
        title=f"第 {episode_no} 集",
        file_name=f"e{episode_no}.mp4",
        cos_key=f"kb/{source_id}/{episode_no}/e{episode_no}.mp4",
        file_size=file_size,
        file_hash=hash_,
        deleted_at=utc_now() if deleted else None,
    )
    session.add(row)
    await session.flush()
    return row


# ---------- source_service ----------


async def test_create_source_and_update(session: AsyncSession) -> None:
    view = await source_service.create_source(
        session,
        KbSourceCreateRequest(sourceType="course", name="价值投资课"),
        actor_id=1,
    )
    assert view.id is not None
    assert view.storage_bytes == 0

    updated = await source_service.update_source(
        session,
        view.id,
        KbSourceUpdateRequest(name="价值投资课·二季", enabled=False),
        actor_id=1,
    )
    assert updated.name == "价值投资课·二季"
    assert updated.enabled is False
    assert updated.author is None


async def test_soft_delete_and_restore_source(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, file_size=500)
    src_row = await session.get(KbSource, src.id)
    src_row.storage_bytes = 500
    await session.commit()

    with _patch_lock():
        await source_service.soft_delete_source(session, src.id, actor_id=1)

    with pytest.raises(NotFoundError):
        await source_service.get_source(session, src.id)
    rows = (await session.execute(select(KbMedia))).scalars().all()
    assert all(m.deleted_at is not None for m in rows)
    after = await session.get(KbSource, src.id)
    assert after.storage_bytes == 0
    assert after.pending_cleanup_bytes == 500

    restored = await source_service.restore_source(session, src.id, actor_id=1)
    assert restored.deleted_at is None
    assert restored.pending_cleanup_bytes == 0
    media_row = await session.get(KbMedia, media.id)
    assert media_row.deleted_at is None


async def test_soft_delete_source_lock_busy(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    with _patch_lock(acquired=False), pytest.raises(ConflictError):
        await source_service.soft_delete_source(session, src.id, actor_id=1)


async def test_restore_source_outside_window(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    row = await session.get(KbSource, src.id)
    row.deleted_at = utc_now() - timedelta(hours=25)
    await session.commit()
    with pytest.raises(NotFoundError, match="恢复窗口"):
        await source_service.restore_source(session, src.id, actor_id=1)


async def test_source_actions_record_audit(session: AsyncSession) -> None:
    view = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="book", name="书"), actor_id=7
    )
    with _patch_lock():
        await source_service.soft_delete_source(session, view.id, actor_id=7)
    actions = (
        (await session.execute(select(AdminAuditLog.action).order_by(AdminAuditLog.id)))
        .scalars()
        .all()
    )
    assert actions == ["kb.source.create", "kb.source.delete"]


# ---------- media_service.init_uploads ----------


async def test_init_uploads_keeps_chinese_name_and_relative_path(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    item = KbMediaInitItem(
        fileName="3.板块效应2.mp4",
        relativePath="第3章/3.板块效应2.mp4",
        size=100,
        hash="d" * 32,
        mediaKind="video",
    )
    cm, _ = _patch_minio()
    with cm:
        await media_service.init_uploads(
            session, src.id, KbMediaInitRequest(items=[item]), actor_id=1
        )
    row = (await media_repository_all(session))[0]
    # 展示名保留原始字符；COS key 收敛为 ASCII；目录结构落库
    assert row.file_name == "3.板块效应2.mp4"
    assert row.title == "3.板块效应2"
    assert row.relative_path == "第3章/3.板块效应2.mp4"
    assert row.cos_key == f"kb/{src.id}/{row.id}/3._2.mp4"


async def test_init_uploads_auto_episode_and_presign(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    await _seed_media(session, src.id, episode_no=2)
    data = KbMediaInitRequest(
        items=[_init_item("L03.mp4"), _init_item("L04.mp4", hash_="c" * 32)]
    )
    cm, _ = _patch_minio()
    with cm:
        resp = await media_service.init_uploads(
            session, src.id, data, actor_id=1
        )
    assert [r.media_id for r in resp.items] == [2, 3]
    rows = await media_repository_all(session)
    new_rows = {r.id: r for r in rows if r.id in (2, 3)}
    assert new_rows[2].episode_no == 3
    assert new_rows[3].episode_no == 4
    assert new_rows[2].cos_key == f"kb/{src.id}/2/L03.mp4"


async def media_repository_all(session: AsyncSession) -> list[KbMedia]:
    return list((await session.execute(select(KbMedia))).scalars().all())


async def test_init_uploads_book_has_no_episode(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="book", name="书"), actor_id=1
    )
    data = KbMediaInitRequest(items=[_init_item("a.pdf", media_kind="book")])
    cm, _ = _patch_minio()
    with cm:
        resp = await media_service.init_uploads(session, src.id, data, actor_id=1)
    assert len(resp.items) == 1
    row = (await media_repository_all(session))[0]
    assert row.episode_no is None
    assert row.media_kind == "book"


async def test_init_uploads_rejects_batch_hash_dup(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    data = KbMediaInitRequest(
        items=[_init_item("a.mp4"), _init_item("b.mp4", episode_no=2)]
    )
    with pytest.raises(ConflictError) as exc_info:
        await media_service.init_uploads(session, src.id, data, actor_id=1)
    msg = str(exc_info.value)
    assert "哈希重复" in msg
    assert "a.mp4" in msg and "b.mp4" in msg


async def test_init_uploads_marks_existing_hash_as_conflict(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    await _seed_media(session, src.id, episode_no=1, hash_="a" * 32)
    cm, minio = _patch_minio()
    with cm:
        resp = await media_service.init_uploads(
            session,
            src.id,
            KbMediaInitRequest(items=[_init_item("dup.mp4", hash_="a" * 32)]),
            actor_id=1,
        )
    result = resp.items[0]
    assert result.media_id is None
    assert result.upload_url is None
    assert result.conflict_with is not None
    assert "第 1 集" in result.conflict_with
    minio.presigned_put_url.assert_not_awaited()


async def test_init_uploads_mixed_batch_conflict_and_created(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    await _seed_media(session, src.id, episode_no=1, hash_="a" * 32)
    data = KbMediaInitRequest(
        items=[_init_item("dup.mp4", hash_="a" * 32), _init_item("new.mp4", hash_="c" * 32)]
    )
    cm, minio = _patch_minio()
    with cm:
        resp = await media_service.init_uploads(session, src.id, data, actor_id=1)
    assert [r.conflict_with is not None for r in resp.items] == [True, False]
    assert resp.items[0].media_id is None
    assert resp.items[1].media_id is not None
    assert resp.items[1].upload_url == "https://cos/put"
    minio.presigned_put_url.assert_awaited_once()


async def test_init_uploads_adopts_orphan_row(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    orphan = await _seed_media(
        session, src.id, episode_no=1, hash_="a" * 32, file_size=0
    )
    data = KbMediaInitRequest(items=[_init_item("reupload.mp4", hash_="a" * 32)])
    cm, minio = _patch_minio()
    with cm:
        resp = await media_service.init_uploads(session, src.id, data, actor_id=1)

    assert [r.media_id for r in resp.items] == [orphan.id]
    rows = await media_repository_all(session)
    assert len(rows) == 1
    row = rows[0]
    assert row.file_name == "reupload.mp4"
    assert row.episode_no == 1
    assert row.media_kind == "video"
    assert row.cos_key == f"kb/{src.id}/{orphan.id}/reupload.mp4"
    minio.presigned_put_url.assert_awaited_once()

    audits = (
        (await session.execute(select(AdminAuditLog).order_by(AdminAuditLog.id)))
        .scalars()
        .all()
    )
    init_audit = next(a for a in audits if a.action == "kb.media.init")
    assert init_audit.detail["adoptedMediaIds"] == [orphan.id]


async def test_init_uploads_skips_deleted_orphan(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    deleted = await _seed_media(
        session, src.id, episode_no=1, hash_="c" * 32, file_size=0, deleted=True
    )
    data = KbMediaInitRequest(items=[_init_item("dup.mp4", hash_="c" * 32)])
    cm, _ = _patch_minio()
    with cm:
        resp = await media_service.init_uploads(session, src.id, data, actor_id=1)

    rows = await media_repository_all(session)
    assert len(rows) == 2
    assert resp.items[0].media_id != deleted.id


async def test_init_uploads_episode_conflict_rolls_back(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    await _seed_media(session, src.id, episode_no=1)
    data = KbMediaInitRequest(
        items=[_init_item("new.mp4", hash_="c" * 32, episode_no=1)]
    )
    with pytest.raises(ConflictError, match="集号"):
        await media_service.init_uploads(session, src.id, data, actor_id=1)
    names = [m.file_name for m in await media_repository_all(session)]
    assert "new.mp4" not in names


# ---------- media_service.confirm_uploaded ----------


async def _uploaded_fixture(session: AsyncSession) -> tuple[KbSource, KbMedia]:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, episode_no=1)
    return src, media


async def test_confirm_uploaded_success(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, episode_no=1, hash_="ab" * 16)
    cm, _ = _patch_minio(stat=(1234, "ab" * 16))
    with cm:
        view = await media_service.confirm_uploaded(session, media.id, actor_id=1)
    assert view.file_size == 1234
    src_row = await session.get(KbSource, src.id)
    assert src_row.storage_bytes == 1234
    assert view.process_status == "uploaded"


async def test_confirm_uploaded_missing_object(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id)
    cm, _ = _patch_minio(stat=None)
    with cm, pytest.raises(UnprocessableEntityError, match="尚未上传"):
        await media_service.confirm_uploaded(session, media.id, actor_id=1)


async def test_confirm_uploaded_etag_mismatch_removes_object(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, hash_="ab" * 16)
    cm, minio = _patch_minio(stat=(999, "cd" * 16))
    with cm:
        with pytest.raises(UnprocessableEntityError, match="md5"):
            await media_service.confirm_uploaded(session, media.id, actor_id=1)
        minio.remove_files.assert_awaited_once()


async def test_confirm_uploaded_hash_conflict_removes_object(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    # 存活行哈希唯一由 DB 部分索引兜底，此处桩掉仓储查询模拟冲突命中
    dup = await _seed_media(session, src.id, episode_no=2, hash_="ab" * 16, file_size=0)
    cm, minio = _patch_minio(stat=(100, "ab" * 16))
    conflict = MagicMock(title="第 1 集", episode_no=1)
    with cm:
        with patch(
            "app.services.kb.media_service.media_repository.find_hash_conflict",
            new=AsyncMock(return_value=conflict),
        ):
            with pytest.raises(ConflictError, match="内容重复"):
                await media_service.confirm_uploaded(session, dup.id, actor_id=1)
        minio.remove_files.assert_awaited_once()


# ---------- media_service.patch / soft delete / restore ----------


async def test_patch_media_episode_conflict(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    await _seed_media(session, src.id, episode_no=1)
    m2 = await _seed_media(session, src.id, episode_no=2, hash_="cd" * 16)
    with pytest.raises(ConflictError, match="集号 1"):
        await media_service.patch_media(
            session, m2.id, KbMediaPatchRequest(episodeNo=1), actor_id=1
        )


async def test_requeue_failed_media(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id)
    media.process_status = KbProcessStatus.FAILED
    media.process_error = "asr_http_500"
    await session.commit()

    view = await media_service.requeue_failed_media(session, media.id, actor_id=1)
    assert view.process_status == KbProcessStatus.QUEUED
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.QUEUED
    assert row.process_error is None

    # 非失败状态拒绝重排队
    with pytest.raises(ConflictError, match="仅失败素材"):
        await media_service.requeue_failed_media(session, media.id, actor_id=1)


async def test_soft_delete_and_restore_media_accounting(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, file_size=700)
    src_row = await session.get(KbSource, src.id)
    src_row.storage_bytes = 700
    await session.commit()

    await media_service.soft_delete_media(session, media.id, actor_id=1)
    after = await session.get(KbSource, src.id)
    assert after.storage_bytes == 0
    assert after.pending_cleanup_bytes == 700
    with pytest.raises(NotFoundError):
        await media_service.get_media(session, media.id)

    restored = await media_service.restore_media(session, media.id, actor_id=1)
    assert restored.deleted_at is None
    after = await session.get(KbSource, src.id)
    assert after.storage_bytes == 700
    assert after.pending_cleanup_bytes == 0


async def test_restore_media_outside_window(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, deleted=True)
    row = await session.get(KbMedia, media.id)
    row.deleted_at = utc_now() - timedelta(hours=25)
    await session.commit()
    with pytest.raises(NotFoundError, match="恢复窗口"):
        await media_service.restore_media(session, media.id, actor_id=1)


async def test_list_media_hides_deleted_and_counts(session: AsyncSession) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    live = await _seed_media(session, src.id, episode_no=1, file_size=100)
    await _seed_media(session, src.id, episode_no=2, hash_="cd" * 16, deleted=True)
    src_row = await session.get(KbSource, src.id)
    src_row.storage_bytes = 100
    await session.commit()

    views = await media_service.list_media(session, src.id)
    assert [v.id for v in views] == [live.id]
    assert views[0].file_size == 100


# ---------- media_service.upload_session（分片直传）----------


def _multipart_minio(cm_stat: tuple[int, str] | None = (100, "x" * 32)):
    cm, minio = _patch_minio(stat=cm_stat)
    minio.create_multipart_upload = AsyncMock(return_value="uid-1")
    minio.list_multipart_parts = AsyncMock(return_value=[])
    minio.complete_multipart_upload = AsyncMock(return_value=None)
    minio.abort_multipart_upload = AsyncMock(return_value=None)
    minio.presigned_part_url = AsyncMock(
        side_effect=lambda _key, _uid, n, _ttl: f"https://cos/part{n}"
    )
    return cm, minio


async def test_create_upload_session_fresh_signs_all_parts(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, episode_no=1, file_size=0)
    media.process_meta = {"declaredSize": 100}
    await session.commit()
    cm, minio = _multipart_minio()
    with cm:
        resp = await media_service.create_upload_session(
            session,
            media.id,
            KbUploadSessionRequest(partSize=16 * 1024 * 1024, partCount=3),
            actor_id=1,
        )
    assert resp.upload_id == "uid-1"
    assert [p.part_number for p in resp.part_urls] == [1, 2, 3]
    assert resp.completed_parts == []
    minio.create_multipart_upload.assert_awaited_once()
    row = await session.get(KbMedia, media.id)
    assert row.process_meta["uploadId"] == "uid-1"
    assert row.process_meta["declaredSize"] == 100


async def test_create_upload_session_resumes_and_signs_missing_only(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, episode_no=1, file_size=0)
    media.process_meta = {"uploadId": "uid-old", "declaredSize": 100}
    await session.commit()
    cm, minio = _multipart_minio()
    minio.list_multipart_parts = AsyncMock(
        return_value=[MultipartPart(part_number=1, etag="aa", size=60)]
    )
    with cm:
        resp = await media_service.create_upload_session(
            session,
            media.id,
            KbUploadSessionRequest(
                partSize=16 * 1024 * 1024,
                partCount=2,
                resumeUploadId="uid-stale-local",
            ),
            actor_id=1,
        )
    # 服务端真相续传：已完成第 1 片，仅签发缺失分片
    minio.create_multipart_upload.assert_not_awaited()
    assert [p.part_number for p in resp.completed_parts] == [1]
    assert [p.part_number for p in resp.part_urls] == [2]


async def test_confirm_uploaded_multipart_completes_and_accounts(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, episode_no=1, file_size=0)
    media.process_meta = {
        "uploadId": "uid-1",
        "partSize": 16 * 1024 * 1024,
        "partCount": 2,
        "sessionStartedAt": utc_now().isoformat(),
        "declaredSize": 100,
    }
    await session.commit()
    cm, minio = _multipart_minio(cm_stat=(100, "abc-2"))
    minio.list_multipart_parts = AsyncMock(
        return_value=[
            MultipartPart(part_number=2, etag="bb", size=40),
            MultipartPart(part_number=1, etag="aa", size=60),
        ]
    )
    with cm:
        view = await media_service.confirm_uploaded(session, media.id, actor_id=1)
    assert view.file_size == 100
    minio.complete_multipart_upload.assert_awaited_once()
    parts_arg = minio.complete_multipart_upload.await_args.args[2]
    assert [p.part_number for p in parts_arg] == [1, 2]
    row = await session.get(KbMedia, media.id)
    # 会话键清除，declaredSize 保留作审计
    assert "uploadId" not in row.process_meta
    assert row.process_meta["declaredSize"] == 100
    src_row = await session.get(KbSource, src.id)
    assert src_row.storage_bytes == 100


async def test_confirm_uploaded_multipart_incomplete_rejects(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, episode_no=1, file_size=0)
    media.process_meta = {"uploadId": "uid-1", "declaredSize": 100}
    await session.commit()
    cm, minio = _multipart_minio()
    minio.list_multipart_parts = AsyncMock(
        return_value=[MultipartPart(part_number=1, etag="aa", size=60)]
    )
    with cm, pytest.raises(UnprocessableEntityError, match="尚未传齐"):
        await media_service.confirm_uploaded(session, media.id, actor_id=1)
    minio.complete_multipart_upload.assert_not_awaited()


async def test_abort_upload_session_releases_and_clears(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, episode_no=1, file_size=0)
    media.process_meta = {"uploadId": "uid-1", "partSize": 123, "declaredSize": 100}
    await session.commit()
    cm, minio = _multipart_minio()
    with cm:
        await media_service.abort_upload_session(session, media.id, actor_id=1)
    minio.abort_multipart_upload.assert_awaited_once()
    row = await session.get(KbMedia, media.id)
    assert "uploadId" not in row.process_meta
    assert row.process_meta["declaredSize"] == 100
