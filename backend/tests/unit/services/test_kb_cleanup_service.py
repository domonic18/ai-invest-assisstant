"""知识库物理清理服务单测：过窗软删清除、超龄分片会话 abort、deep 孤儿扫描。"""

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.clock import utc_now
from app.core.database import Base
from app.models.kb import KbMedia, KbSource
from app.services.kb import cleanup_service

pytestmark = pytest.mark.unit


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[KbSource.__table__, KbMedia.__table__]
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
        "app.services.kb.cleanup_service.redis_lock",
        side_effect=fake_lock,
    )


def _patch_deep_slot(available: bool = True):
    client = MagicMock()
    client.set = AsyncMock(return_value=available)
    return (
        patch(
            "app.services.kb.cleanup_service.get_redis", return_value=client
        ),
        client,
    )


def _patch_minio() -> tuple[Any, MagicMock]:
    minio = MagicMock()
    minio.remove_files = AsyncMock(return_value=None)
    minio.abort_multipart_upload = AsyncMock(return_value=None)
    minio.list_object_names = AsyncMock(return_value=[])
    cm = patch(
        "app.services.kb.cleanup_service.get_minio_service", return_value=minio
    )
    return cm, minio


async def _seed_source(session: AsyncSession, *, pending: int = 0) -> KbSource:
    src = KbSource(
        source_type="course",
        name="课",
        pending_cleanup_bytes=pending,
    )
    session.add(src)
    await session.commit()
    return src


async def _seed_media(
    session: AsyncSession,
    source_id: int,
    *,
    hash_: str = "b" * 32,
    file_size: int = 500,
    deleted: bool = False,
    cos_key: str | None = None,
    process_status: str = "ready",
    process_meta: dict[str, Any] | None = None,
) -> KbMedia:
    media = KbMedia(
        source_id=source_id,
        media_kind="video",
        title="第 1 集",
        file_name="L01.mp4",
        cos_key=cos_key or f"kb/{source_id}/L01.mp4",
        file_size=file_size,
        file_hash=hash_,
        process_status=process_status,
        process_meta=process_meta or {},
        deleted_at=utc_now() if deleted else None,
    )
    session.add(media)
    await session.commit()
    return media


async def test_soft_deleted_media_past_window_purged(session: AsyncSession) -> None:
    src = await _seed_source(session, pending=500)
    media = await _seed_media(session, src.id)
    media.deleted_at = utc_now() - timedelta(hours=25)
    await session.commit()

    cm, minio = _patch_minio()
    with cm, _patch_lock():
        stats = await cleanup_service.run_cleanup(session)

    assert stats["purgedMedia"] == 1
    assert stats["purgedBytes"] == 500
    minio.remove_files.assert_awaited_once_with([media.cos_key])
    assert await session.get(KbMedia, media.id) is None
    src_row = await session.get(KbSource, src.id)
    assert src_row.pending_cleanup_bytes == 0


async def test_recent_soft_delete_kept(session: AsyncSession) -> None:
    src = await _seed_source(session, pending=500)
    media = await _seed_media(session, src.id, deleted=True)

    cm, minio = _patch_minio()
    with cm, _patch_lock():
        stats = await cleanup_service.run_cleanup(session)

    assert stats["purgedMedia"] == 0
    minio.remove_files.assert_not_awaited()
    assert await session.get(KbMedia, media.id) is not None


async def test_source_past_window_cascades_medias(session: AsyncSession) -> None:
    src = await _seed_source(session)
    media = await _seed_media(session, src.id, hash_="c" * 32)
    src.deleted_at = utc_now() - timedelta(hours=25)
    await session.commit()

    cm, minio = _patch_minio()
    with cm, _patch_lock():
        stats = await cleanup_service.run_cleanup(session)

    assert stats["purgedSources"] == 1
    assert stats["purgedMedia"] == 1
    minio.remove_files.assert_awaited_once_with([media.cos_key])
    assert await session.get(KbSource, src.id) is None
    assert await session.get(KbMedia, media.id) is None


async def test_stale_upload_session_aborted(session: AsyncSession) -> None:
    src = await _seed_source(session)
    stale_started = (utc_now() - timedelta(days=8)).isoformat()
    stale = await _seed_media(
        session,
        src.id,
        hash_="d" * 32,
        file_size=0,
        process_status="uploaded",
        process_meta={
            "uploadId": "uid-old",
            "sessionStartedAt": stale_started,
            "declaredSize": 100,
        },
    )
    fresh = await _seed_media(
        session,
        src.id,
        hash_="e" * 32,
        file_size=0,
        process_status="uploaded",
        process_meta={
            "uploadId": "uid-new",
            "sessionStartedAt": utc_now().isoformat(),
        },
    )

    cm, minio = _patch_minio()
    with cm, _patch_lock():
        stats = await cleanup_service.run_cleanup(session)

    assert stats["abortedSessions"] == 1
    minio.abort_multipart_upload.assert_awaited_once_with(stale.cos_key, "uid-old")
    stale_row = await session.get(KbMedia, stale.id)
    assert "uploadId" not in stale_row.process_meta
    assert stale_row.process_meta["declaredSize"] == 100
    fresh_row = await session.get(KbMedia, fresh.id)
    assert fresh_row.process_meta["uploadId"] == "uid-new"


async def test_deep_scan_removes_orphan_objects(session: AsyncSession) -> None:
    src = await _seed_source(session)
    live = await _seed_media(
        session, src.id, hash_="f" * 32, cos_key="kb/1/live.mp4"
    )
    soft_deleted = await _seed_media(
        session,
        src.id,
        hash_="9" * 32,
        cos_key="kb/1/soft.mp4",
        deleted=True,
    )

    cm, minio = _patch_minio()
    minio.list_object_names = AsyncMock(
        return_value=[
            ("kb/1/live.mp4", 500),
            ("kb/1/soft.mp4", 300),
            ("kb/9/orphan.mp4", 42),
        ]
    )
    slot_cm, _client = _patch_deep_slot(available=True)
    with cm, _patch_lock(), slot_cm:
        stats = await cleanup_service.run_cleanup(session, deep=True)

    # 软删未过窗的行仍引用对象，不算孤儿
    assert stats["orphanObjects"] == 1
    assert stats["orphanBytes"] == 42
    minio.remove_files.assert_awaited_once_with(["kb/9/orphan.mp4"])
    assert await session.get(KbMedia, live.id) is not None
    assert await session.get(KbMedia, soft_deleted.id) is not None


async def test_deep_scan_skipped_when_daily_slot_taken(session: AsyncSession) -> None:
    src = await _seed_source(session)
    await _seed_media(session, src.id, hash_="a" * 32)

    cm, minio = _patch_minio()
    slot_cm, client = _patch_deep_slot(available=False)
    with cm, _patch_lock(), slot_cm:
        stats = await cleanup_service.run_cleanup(session, deep=True)

    assert stats["orphanObjects"] == 0
    minio.list_object_names.assert_not_awaited()
    client.set.assert_awaited_once()


async def test_busy_lock_skips_round(session: AsyncSession) -> None:
    src = await _seed_source(session)
    await _seed_media(session, src.id, deleted=True)

    cm, minio = _patch_minio()
    with cm, _patch_lock(acquired=False):
        stats = await cleanup_service.run_cleanup(session)

    assert stats == {"skippedBusy": 1}
    minio.remove_files.assert_not_awaited()
