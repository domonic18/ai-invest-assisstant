"""视觉通道编排单测：选帧落库、描述计费、失败退避与任务薄壳（ffmpeg/VLM 全 mock）。"""

from contextlib import ExitStack, asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.clock import utc_now
from app.core.database import Base
from app.core.exceptions import ConflictError, UnprocessableEntityError
from app.models.kb import KbImageAsset, KbMedia, KbSource, KbTranscriptSegment
from app.schemas.kb import ImageUnderstanding
from app.services.kb import vision_extract, vision_service

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
                KbImageAsset.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed_media(
    db: AsyncSession,
    *,
    vision_done: bool = False,
    process_meta: dict[str, Any] | None = None,
) -> KbMedia:
    src = KbSource(source_type="course", name="课")
    db.add(src)
    await db.flush()
    media = KbMedia(
        source_id=src.id,
        media_kind="video",
        episode_no=1,
        title="第 1 集",
        file_name="e1.mp4",
        cos_key=f"kb/{src.id}/1/e1.mp4",
        file_size=100,
        file_hash="a" * 32,
        duration_seconds=600,
        process_status="done",
        vision_at=utc_now() if vision_done else None,
        process_meta=process_meta or {},
    )
    db.add(media)
    await db.flush()
    db.add(
        KbTranscriptSegment(
            source_id=src.id,
            media_id=media.id,
            seq_no=0,
            text="你看这条线的支撑非常明显",
            start_ms=0,
            end_ms=60_000,
        )
    )
    db.add(
        KbTranscriptSegment(
            source_id=src.id,
            media_id=media.id,
            seq_no=1,
            text="第二句普通讲解",
            start_ms=60_000,
            end_ms=120_000,
        )
    )
    await db.commit()
    return media


def _minio_mock() -> MagicMock:
    minio = MagicMock()
    minio.download_file = AsyncMock(return_value=b"video-bytes")
    minio.upload_file = AsyncMock(return_value="key")
    minio.get_presigned_url = AsyncMock(return_value="https://signed/thumb.jpg")
    return minio


def _patches(
    structured: AsyncMock,
    minio: MagicMock | None = None,
    *,
    resolve: AsyncMock | None = None,
) -> dict:
    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield True

    return {
        "lock": patch(
            "app.services.kb.vision_extract.redis_lock", side_effect=fake_lock
        ),
        "resolve_role": patch(
            "app.services.kb.vision_extract.resolve_role_model",
            new=resolve or AsyncMock(return_value=SimpleNamespace(id=99)),
        ),
        "minio": _minio_cm(minio),
        "probe": patch(
            "app.services.kb.vision_extract._probe_duration",
            new=AsyncMock(return_value=100.0),
        ),
        "scenes": patch(
            "app.services.kb.vision_extract._detect_scenes",
            new=AsyncMock(return_value=[120.0]),
        ),
        "jpeg": patch(
            "app.services.kb.vision_extract._extract_jpeg",
            new=AsyncMock(return_value=b"jpeg-bytes"),
        ),
        "phash": patch(
            "app.services.kb.vision_extract._frame_phash",
            new=AsyncMock(side_effect=[0b1111_0000, 0b1111_0000, 0b0000_1111]),
        ),
        "structured": patch(
            "app.agent.runtime.structured.run_structured", new=structured
        ),
    }


def _minio_cm(minio: MagicMock | None) -> Any:
    """选帧与描述两模块各自取 minio 服务，同一 mock 实例覆盖两条路径。"""
    stack = ExitStack()
    chosen = minio or _minio_mock()
    for target in (
        "app.services.kb.vision_extract.get_minio_service",
        "app.services.kb.vision_describe.get_minio_service",
    ):
        stack.enter_context(patch(target, return_value=chosen))
    return stack


async def test_frame_and_describe_full_flow(session: AsyncSession) -> None:
    media = await _seed_media(session)
    structured = AsyncMock(
        return_value=ImageUnderstanding(
            text_in_image="MA5", caption="支撑线讲解", description="K 线支撑位画线"
        )
    )
    patches = _patches(structured)
    with patches["lock"], patches["resolve_role"], patches["minio"], \
         patches["probe"], patches["scenes"], patches["jpeg"], \
         patches["phash"], patches["structured"]:
        stats = await vision_extract.run_vision(session)

    # 候选：guide 30s + fixed 60s（scene 120s 超出 probe 时长 100s 被丢；
    # 第二段文稿无视觉指涉不引导）→ 第 2 帧 phash 与首帧近重复被滤 → 1 帧入库
    assert stats["mediasFramed"] == 1
    assert stats["framesCreated"] == 1
    assert stats["framesDescribed"] == 1
    rows = (
        (await session.execute(select(KbImageAsset).order_by(KbImageAsset.start_ms)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    first = rows[0]
    assert first.start_ms == 28_000  # seek = 30s - 2s 容差
    assert first.page_no is None
    assert first.describe_status == "done"
    assert first.embedding_dirty is True
    assert first.text_in_image == "MA5"
    assert first.cos_key.endswith("/frames/000000028000.jpg")
    assert first.thumb_cos_key.endswith("_thumb.jpg")
    row = await session.get(KbMedia, media.id)
    assert row.vision_at is not None


async def test_describe_failure_backoff_then_terminal(session: AsyncSession) -> None:
    media = await _seed_media(session, vision_done=True)
    session.add(
        KbImageAsset(
            source_id=media.source_id,
            media_id=media.id,
            page_no=None,
            start_ms=5_000,
            cos_key=f"kb/derived/{media.id}/frames/000000005000.jpg",
            thumb_cos_key=f"kb/derived/{media.id}/frames/000000005000_thumb.jpg",
            describe_status="pending",
            describe_attempts=2,
            embedding_dirty=False,
        )
    )
    await session.commit()
    structured = AsyncMock(side_effect=RuntimeError("VLM 渠道 5xx"))
    patches = _patches(structured)
    with patches["lock"], patches["resolve_role"], patches["minio"], \
         patches["structured"]:
        stats = await vision_extract.run_vision(session)

    assert stats["describeFailed"] == 1
    row = (
        (await session.execute(select(KbImageAsset))).scalars().one()
    )
    assert row.describe_attempts == 3
    assert row.describe_status == "failed"
    assert row.vision_description is None


async def test_frame_failure_records_attempts(session: AsyncSession) -> None:
    media = await _seed_media(session)
    media_id = media.id
    structured = AsyncMock()
    patches = _patches(structured)
    patches["scenes"] = patch(
        "app.services.kb.vision_extract._detect_scenes",
        new=AsyncMock(side_effect=RuntimeError("ffmpeg_scene_detect_failed")),
    )
    with patches["lock"], patches["resolve_role"], patches["minio"], \
         patches["probe"], patches["scenes"], patches["structured"]:
        stats = await vision_extract.run_vision(session)

    assert stats["failedMedias"] == 1
    row = await session.get(KbMedia, media_id)
    assert row.vision_at is None
    assert row.process_meta["visionAttempts"] == 1
    assert "scene_detect" in row.process_meta["visionError"]


async def test_skip_media_after_max_attempts(session: AsyncSession) -> None:
    await _seed_media(
        session, process_meta={"visionAttempts": 3, "visionError": "旧错"}
    )
    structured = AsyncMock()
    patches = _patches(structured)
    with patches["lock"], patches["resolve_role"], patches["minio"], \
         patches["probe"], patches["scenes"], patches["jpeg"], \
         patches["phash"], patches["structured"]:
        stats = await vision_extract.run_vision(session)

    assert stats["mediasFramed"] == 0
    assert stats["framesDescribed"] == 0


async def test_no_model_configured(session: AsyncSession) -> None:
    await _seed_media(session)
    patches = _patches(
        AsyncMock(), resolve=AsyncMock(side_effect=UnprocessableEntityError("未配置"))
    )
    with patches["lock"], patches["resolve_role"], patches["minio"]:
        assert await vision_extract.run_vision(session) == {"noModelConfigured": 1}


async def test_busy_lock(session: AsyncSession) -> None:
    await _seed_media(session)

    @asynccontextmanager
    async def busy_lock(*args: Any, **kwargs: Any):
        yield False

    with patch("app.services.kb.vision_extract.redis_lock", side_effect=busy_lock):
        assert await vision_extract.run_vision(session) == {"skippedBusy": 1}


async def test_list_images_signs_thumbnails(session: AsyncSession) -> None:
    media = await _seed_media(session, vision_done=True)
    session.add(
        KbImageAsset(
            source_id=media.source_id,
            media_id=media.id,
            page_no=None,
            start_ms=5_000,
            cos_key=f"kb/derived/{media.id}/frames/000000005000.jpg",
            thumb_cos_key=f"kb/derived/{media.id}/frames/000000005000_thumb.jpg",
            describe_status="done",
            describe_attempts=0,
            embedding_dirty=True,
        )
    )
    await session.commit()
    with patch(
        "app.services.kb.vision_service.get_minio_service",
        return_value=_minio_mock(),
    ):
        result = await vision_service.list_images(session, media.source_id)

    assert result.total == 1
    assert result.items[0].thumb_url == "https://signed/thumb.jpg"
    assert result.items[0].start_ms == 5_000


async def _seed_done_image(db: AsyncSession, media: KbMedia) -> KbImageAsset:
    row = KbImageAsset(
        source_id=media.source_id,
        media_id=media.id,
        page_no=None,
        start_ms=5_000,
        cos_key=f"kb/derived/{media.id}/frames/000000005000.jpg",
        thumb_cos_key=f"kb/derived/{media.id}/frames/000000005000_thumb.jpg",
        describe_status="done",
        describe_attempts=1,
        text_in_image="旧文字",
        caption="旧图注",
        vision_description="旧描述",
        embedding_dirty=False,
    )
    db.add(row)
    await db.commit()
    return row


async def test_redescribe_resets_fields(session: AsyncSession) -> None:
    media = await _seed_media(session, vision_done=True)
    image = await _seed_done_image(session, media)
    with (
        patch(
            "app.services.kb.vision_service.record_audit", new=AsyncMock()
        ) as p_audit,
        patch(
            "app.services.kb.vision_service.get_minio_service",
            return_value=_minio_mock(),
        ),
    ):
        out = await vision_service.redescribe_image(session, image.id, actor_id=1)

    assert out.describe_status == "pending"
    row = await session.get(KbImageAsset, image.id)
    assert row.text_in_image is None
    assert row.caption is None
    assert row.vision_description is None
    assert row.describe_attempts == 0
    assert row.embedding_dirty is True
    assert p_audit.call_args.kwargs["action"] == vision_service.AUDIT_IMAGE_REDESCRIBE


async def test_redescribe_rejects_book_image(session: AsyncSession) -> None:
    src = KbSource(source_type="book", name="书")
    session.add(src)
    await session.flush()
    media = KbMedia(
        source_id=src.id,
        media_kind="book",
        title="书",
        file_name="b.pdf",
        cos_key=f"kb/{src.id}/0/b.pdf",
        file_size=10,
        file_hash="b" * 32,
        process_status="done",
        process_meta={},
    )
    session.add(media)
    await session.flush()
    image = await _seed_done_image(session, media)
    with pytest.raises(ConflictError):
        await vision_service.redescribe_image(session, image.id, actor_id=1)


async def test_set_image_excluded_toggle_and_idempotent(
    session: AsyncSession,
) -> None:
    media = await _seed_media(session, vision_done=True)
    image = await _seed_done_image(session, media)
    with (
        patch(
            "app.services.kb.vision_service.record_audit", new=AsyncMock()
        ) as p_audit,
        patch(
            "app.services.kb.vision_service.get_minio_service",
            return_value=_minio_mock(),
        ),
    ):
        out = await vision_service.set_image_excluded(
            session, image.id, True, actor_id=1
        )
        assert out.index_excluded is True
        row = await session.get(KbImageAsset, image.id)
        assert row.index_excluded is True
        assert row.embedding_dirty is True

        again = await vision_service.set_image_excluded(
            session, image.id, True, actor_id=1
        )
        assert again.index_excluded is True

        restored = await vision_service.set_image_excluded(
            session, image.id, False, actor_id=1
        )
        assert restored.index_excluded is False

    assert p_audit.await_count == 2  # 幂等重复调用不产生第二条审计


async def test_list_images_status_filter(session: AsyncSession) -> None:
    media = await _seed_media(session, vision_done=True)
    done = await _seed_done_image(session, media)
    session.add(
        KbImageAsset(
            source_id=media.source_id,
            media_id=media.id,
            page_no=None,
            start_ms=9_000,
            cos_key=f"kb/derived/{media.id}/frames/000000009000.jpg",
            describe_status="pending",
            describe_attempts=0,
            embedding_dirty=False,
        )
    )
    await session.commit()
    with patch(
        "app.services.kb.vision_service.get_minio_service",
        return_value=_minio_mock(),
    ):
        result = await vision_service.list_images(
            session, media.source_id, status="done"
        )

    assert result.total == 1
    assert result.items[0].id == done.id
    assert result.items[0].index_excluded is False


@pytest.mark.unit
class TestKbVisionSpider:
    async def test_success_with_frames(self) -> None:
        from collector.core.base import CollectStatus
        from collector.spiders.kb_vision import KbVisionCollector

        stats = {"mediasFramed": 1, "framesCreated": 5, "framesDescribed": 5}
        with (
            patch("collector.spiders.kb_vision.AsyncSessionLocal") as mock_factory,
            patch(
                "app.services.kb.vision_extract.run_vision",
                new=AsyncMock(return_value=stats),
            ) as p_run,
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await KbVisionCollector(
                {"source": "internal", "data_type": "kb_vision"}
            ).run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 10
        assert result.metadata == stats
        assert p_run.await_count == 1

    async def test_zero_work_skipped(self) -> None:
        from collector.core.base import CollectStatus
        from collector.spiders.kb_vision import KbVisionCollector

        stats = {
            "mediasFramed": 0,
            "framesCreated": 0,
            "failedMedias": 0,
            "framesDescribed": 0,
            "describeFailed": 0,
        }
        with (
            patch("collector.spiders.kb_vision.AsyncSessionLocal") as mock_factory,
            patch(
                "app.services.kb.vision_extract.run_vision",
                new=AsyncMock(return_value=stats),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await KbVisionCollector(
                {"source": "internal", "data_type": "kb_vision"}
            ).run()

        assert result.status == CollectStatus.SKIPPED
