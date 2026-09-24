"""嵌入物化服务单测：三类脏行增量推进、不可见行清向量、全量重嵌与维度护栏。"""

from contextlib import ExitStack, asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.constants.kb import KB_EMBEDDING_DIMS
from app.core.clock import utc_now
from app.core.database import Base
from app.models.kb import (
    KbImageAsset,
    KbKnowledgePoint,
    KbMedia,
    KbSource,
    KbTranscriptSegment,
)
from app.services.kb import index_service

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
                KbImageAsset.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


# ---------------------------------------------------------------------------
# mock 工具：embedding 客户端 stub / redis 锁
# ---------------------------------------------------------------------------


def _embed_stub(dims: int = KB_EMBEDDING_DIMS) -> MagicMock:
    embed = MagicMock()
    embed.discover_dims = AsyncMock(return_value=dims)

    async def _batched(
        texts: list[str], detail: dict[str, Any] | None = None, timeout: float | None = None
    ) -> list[list[float]]:
        return [[float(len(t) % 7 + 1)] * 8 for t in texts]

    embed.embed_batched = AsyncMock(side_effect=_batched)
    return embed


def _patches(embed: MagicMock) -> list[Any]:
    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield True

    return [
        patch("app.services.kb.index_service.redis_lock", side_effect=fake_lock),
        patch(
            "app.services.kb.index_service.build_embedding_client",
            new=AsyncMock(return_value=embed),
        ),
    ]


async def _seed_media(session: AsyncSession, *, deleted: bool = False) -> KbMedia:
    src = KbSource(source_type="course", name="课")
    session.add(src)
    await session.flush()
    media = KbMedia(
        source_id=src.id,
        media_kind="video",
        episode_no=1,
        title="第 1 集",
        file_name="e1.mp4",
        cos_key=f"kb/{src.id}/e1.mp4",
        file_hash="a" * 32,
        process_status="done",
        deleted_at=utc_now() if deleted else None,
    )
    session.add(media)
    await session.flush()
    return media


# ---------------------------------------------------------------------------
# 增量：可见行写向量、不可见行清向量
# ---------------------------------------------------------------------------


async def test_incremental_embeds_visible_and_clears_invisible(
    session: AsyncSession,
) -> None:
    media = await _seed_media(session)
    pub = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="case",
        title="头肩顶案例",
        term_definition="形态定义",
        body="颈线突破后的量度目标",
        excerpt="头肩顶",
        status="published",
        embedding_dirty=True,
    )
    rej = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="concept",
        title="驳回卡",
        body="旧内容",
        excerpt="旧",
        status="rejected",
        embedding_dirty=True,
    )
    seg = KbTranscriptSegment(
        source_id=media.source_id,
        media_id=media.id,
        seq_no=1,
        text="支撑位与压力位互换",
        start_ms=0,
        end_ms=5000,
    )
    img_ok = KbImageAsset(
        source_id=media.source_id,
        media_id=media.id,
        cos_key="kb/i1",
        describe_status="done",
        text_in_image="头肩顶",
        caption="图注",
        embedding_dirty=True,
    )
    img_ex = KbImageAsset(
        source_id=media.source_id,
        media_id=media.id,
        cos_key="kb/i2",
        describe_status="done",
        caption="被排除",
        embedding_dirty=True,
        index_excluded=True,
    )
    session.add_all([pub, rej, seg, img_ok, img_ex])
    await session.commit()

    embed = _embed_stub()
    with ExitStack() as stack:
        for p in _patches(embed):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["pointsEmbedded"] == 1
    assert stats["pointsCleared"] == 1
    assert stats["segmentsEmbedded"] == 1
    assert stats["imagesEmbedded"] == 1
    assert stats["imagesCleared"] == 1

    # 嵌入输入口径：point 四字段拼接 / segment 原文 / image 三文本拼接
    embedded_texts = [
        t
        for call in embed.embed_batched.call_args_list
        for t in call.args[0]
    ]
    assert "头肩顶案例\n形态定义\n颈线突破后的量度目标" in embedded_texts
    assert "支撑位与压力位互换" in embedded_texts
    assert "头肩顶\n图注" in embedded_texts

    for row in (pub, rej, seg, img_ok, img_ex):
        await session.refresh(row)
        assert row.embedding_dirty is False
    assert pub.embedding is not None and len(pub.embedding) == 8
    assert seg.embedding is not None
    assert img_ok.embedding is not None
    assert rej.embedding is None
    assert img_ex.embedding is None


async def test_incremental_soft_deleted_media_clears_vector(
    session: AsyncSession,
) -> None:
    media = await _seed_media(session, deleted=True)
    point = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="method",
        title="方法卡",
        body="内容",
        excerpt="摘",
        status="published",
        embedding_dirty=True,
    )
    session.add(point)
    await session.commit()

    embed = _embed_stub()
    with ExitStack() as stack:
        for p in _patches(embed):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["pointsEmbedded"] == 0
    assert stats["pointsCleared"] == 1
    await session.refresh(point)
    assert point.embedding_dirty is False
    assert point.embedding is None


async def test_incremental_disabled_source_clears_vector(
    session: AsyncSession,
) -> None:
    """停用知识源的 published 点不进检索面（arch/12 §7.1 enabled=false 口径）。"""
    media = await _seed_media(session)
    source = await session.get(KbSource, media.source_id)
    assert source is not None
    source.enabled = False
    point = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="concept",
        title="停用源卡片",
        body="内容",
        excerpt="摘",
        status="published",
        embedding_dirty=True,
    )
    session.add(point)
    await session.commit()

    embed = _embed_stub()
    with ExitStack() as stack:
        for p in _patches(embed):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["pointsEmbedded"] == 0
    assert stats["pointsCleared"] == 1


async def test_incremental_nothing_dirty_skips_embed(session: AsyncSession) -> None:
    embed = _embed_stub()
    with ExitStack() as stack:
        for p in _patches(embed):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["dirtyPoints"] == 0
    assert stats["dirtySegments"] == 0
    assert stats["dirtyImages"] == 0
    embed.embed_batched.assert_not_awaited()


# ---------------------------------------------------------------------------
# 维度护栏与全量重嵌
# ---------------------------------------------------------------------------


async def test_dimension_mismatch_skips(session: AsyncSession) -> None:
    media = await _seed_media(session)
    session.add(
        KbTranscriptSegment(
            source_id=media.source_id, media_id=media.id, seq_no=1, text="脏行"
        )
    )
    await session.commit()

    embed = _embed_stub(dims=1024)
    with ExitStack() as stack:
        for p in _patches(embed):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["dimensionMismatch"] == 1
    assert stats["expectedDims"] == KB_EMBEDDING_DIMS
    assert stats["actualDims"] == 1024
    embed.embed_batched.assert_not_awaited()
    seg = await session.get(KbTranscriptSegment, 1)
    assert seg is not None
    assert seg.embedding_dirty is True


async def test_force_rebuild_marks_all_and_drains(session: AsyncSession) -> None:
    media = await _seed_media(session)
    clean_point = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="theorem",
        title="已物化卡",
        body="内容",
        excerpt="摘",
        status="published",
        embedding_dirty=False,
        embedding=[0.0] * 8,
    )
    dirty_segment = KbTranscriptSegment(
        source_id=media.source_id,
        media_id=media.id,
        seq_no=1,
        text="脏分段",
        embedding_dirty=True,
    )
    session.add_all([clean_point, dirty_segment])
    await session.commit()

    embed = _embed_stub()
    with ExitStack() as stack:
        for p in _patches(embed):
            stack.enter_context(p)
        stats = await index_service.run_index(session, force_rebuild=True)

    assert stats["forceRebuild"] == 1
    assert stats["phase"] == "rebuild"
    assert stats["pointsEmbedded"] == 1
    assert stats["segmentsEmbedded"] == 1
    await session.refresh(clean_point)
    await session.refresh(dirty_segment)
    # 已物化行被重嵌覆写（旧 [0.0]*8 → stub 非零向量），脏标全清
    assert clean_point.embedding is not None
    assert any(v != 0.0 for v in clean_point.embedding)
    assert clean_point.embedding_dirty is False
    assert dirty_segment.embedding is not None
    assert dirty_segment.embedding_dirty is False
