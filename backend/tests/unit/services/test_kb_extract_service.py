"""抽取编排单测：章节推断、滑窗抽取落库、失败记账与任务薄壳（LLM 全 mock）。"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.clock import utc_now
from app.core.database import Base
from app.core.exceptions import UnprocessableEntityError
from app.models.kb import KbKnowledgePoint, KbMedia, KbSource, KbTranscriptSegment
from app.schemas.kb import (
    ChapterNodeDraft,
    ChapterTreeDraft,
    EpisodeOutline,
    EpisodeOutlinePoint,
    KbExtractionResult,
    KbPointDraft,
)
from app.services.kb import extract_service

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
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed_media(
    db: AsyncSession,
    *,
    episode_no: int = 1,
    status: str = "done",
    extracted: bool = False,
    with_draft: bool = False,
    process_meta: dict[str, Any] | None = None,
) -> KbMedia:
    src = KbSource(source_type="course", name="课")
    if with_draft:
        src.chapter_tree = {
            "draft": [{"id": "1", "title": "已推章节", "children": []}],
            "published": None,
        }
    db.add(src)
    await db.flush()
    media = KbMedia(
        source_id=src.id,
        media_kind="video",
        episode_no=episode_no,
        title=f"第 {episode_no} 集",
        file_name=f"e{episode_no}.mp4",
        cos_key=f"kb/{src.id}/{episode_no}/e{episode_no}.mp4",
        file_size=100,
        file_hash="a" * 32,
        duration_seconds=600,
        process_status=status,
        extracted_at=utc_now() if extracted else None,
        process_meta=process_meta or {},
    )
    db.add(media)
    await db.flush()
    for i in range(3):
        db.add(
            KbTranscriptSegment(
                source_id=src.id,
                media_id=media.id,
                seq_no=i,
                text=f"第{i + 1}句原文",
                start_ms=i * 60_000,
                end_ms=(i + 1) * 60_000,
            )
        )
    await db.commit()
    return media


def _patches(run_structured: AsyncMock, *, resolve: AsyncMock | None = None) -> dict:
    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield True

    return {
        "lock": patch(
            "app.services.kb.extract_service.redis_lock", side_effect=fake_lock
        ),
        "resolve_role": patch(
            "app.services.kb.extract_service.resolve_role_model",
            new=resolve or AsyncMock(return_value=SimpleNamespace(id=99)),
        ),
        "structured": patch(
            "app.agent.runtime.structured.run_structured", new=run_structured
        ),
    }


async def test_infer_chapters_merges_outlines_into_draft(session: AsyncSession) -> None:
    media = await _seed_media(session, episode_no=1, extracted=True)
    src_id = media.source_id
    structured = AsyncMock(
        side_effect=[
            EpisodeOutline(
                episode_no=1,
                points=[EpisodeOutlinePoint(title="复利", summary="利滚利")],
            ),
            ChapterTreeDraft(
                nodes=[ChapterNodeDraft(title="价值篇", children=[ChapterNodeDraft(title="复利", children=[])])]
            ),
        ]
    )
    patches = _patches(structured)
    with patches["lock"], patches["resolve_role"], patches["structured"]:
        stats = await extract_service.run_extraction(session)

    assert stats["chaptersInferred"] == 1
    src = await session.get(KbSource, src_id)
    draft = src.chapter_tree["draft"]
    assert draft[0]["id"] == "1"
    assert draft[0]["children"][0]["id"] == "1.1"
    # 已有 draft 的源下轮不再扫
    with patches["lock"], patches["resolve_role"], patches["structured"]:
        again = await extract_service.run_extraction(session)
    assert again["chaptersInferred"] == 0
    assert structured.await_count == 2


async def test_extract_points_creates_draft_rows(session: AsyncSession) -> None:
    media = await _seed_media(session, with_draft=True)
    src_id = media.source_id
    existing = KbKnowledgePoint(
        source_id=src_id,
        media_id=media.id,
        point_type="concept",
        title="复利",
        body="已有点",
        excerpt="已有点",
        related_ids=[],
        chapter_path=[],
        status="draft",
    )
    session.add(existing)
    await session.commit()
    result = KbExtractionResult(
        points=[
            KbPointDraft(
                title="安全边际",
                body="正文",
                point_type="concept",
                term_definition=None,
                applicable_scene=None,
                excerpt="第1句原文",
                start_ms=0,
                end_ms=60_000,
                related_titles=["复利"],
            ),
            KbPointDraft(
                title="幻觉点",
                body="正文",
                point_type="case",
                term_definition=None,
                applicable_scene=None,
                excerpt="文稿中不存在的摘抄",
                start_ms=None,
                end_ms=None,
                related_titles=[],
            ),
        ]
    )
    structured = AsyncMock(return_value=result)
    patches = _patches(structured)
    with patches["lock"], patches["resolve_role"], patches["structured"]:
        stats = await extract_service.run_extraction(session)

    assert stats["mediasExtracted"] == 1
    assert stats["pointsCreated"] == 2
    row = await session.get(KbMedia, media.id)
    assert row.extracted_at is not None
    points = (
        (
            await session.execute(
                select(KbKnowledgePoint).where(KbKnowledgePoint.media_id == media.id)
            )
        )
        .scalars()
        .all()
    )
    by_title = {p.title: p for p in points}
    hit = by_title["安全边际"]
    assert hit.status == "draft"
    assert hit.needs_review is False
    assert hit.related_ids == [existing.id]
    assert by_title["幻觉点"].needs_review is True
    # 单窗 180s 只调一次 LLM
    assert structured.await_count == 1


async def test_extract_failure_records_attempts(session: AsyncSession) -> None:
    media = await _seed_media(session, with_draft=True)
    media_id = media.id
    structured = AsyncMock(side_effect=RuntimeError("模型超时"))
    patches = _patches(structured)
    with patches["lock"], patches["resolve_role"], patches["structured"]:
        stats = await extract_service.run_extraction(session)

    assert stats["failedMedias"] == 1
    row = await session.get(KbMedia, media_id)
    assert row.extracted_at is None
    assert row.process_meta["extractAttempts"] == 1
    assert "模型超时" in row.process_meta["extractError"]


async def test_extract_skips_media_after_max_attempts(session: AsyncSession) -> None:
    await _seed_media(
        session,
        with_draft=True,
        process_meta={"extractAttempts": 3, "extractError": "旧错"},
    )
    structured = AsyncMock()
    patches = _patches(structured)
    with patches["lock"], patches["resolve_role"], patches["structured"]:
        stats = await extract_service.run_extraction(session)

    assert stats["mediasExtracted"] == 0
    structured.assert_not_awaited()


async def test_extract_no_model_configured(session: AsyncSession) -> None:
    await _seed_media(session)
    patches = _patches(
        AsyncMock(), resolve=AsyncMock(side_effect=UnprocessableEntityError("未配置"))
    )
    with patches["lock"], patches["resolve_role"], patches["structured"]:
        stats = await extract_service.run_extraction(session)

    assert stats == {"noModelConfigured": 1}


async def test_extract_busy_lock(session: AsyncSession) -> None:
    await _seed_media(session)

    @asynccontextmanager
    async def busy_lock(*args: Any, **kwargs: Any):
        yield False

    with (
        patch("app.services.kb.extract_service.redis_lock", side_effect=busy_lock),
    ):
        assert await extract_service.run_extraction(session) == {"skippedBusy": 1}


@pytest.mark.unit
class TestKbExtractSpider:
    async def test_success_with_points(self) -> None:
        from collector.core.base import CollectStatus
        from collector.spiders.kb_extract import KbExtractCollector

        stats = {"chaptersInferred": 1, "mediasExtracted": 2, "pointsCreated": 5}
        with (
            patch("collector.spiders.kb_extract.AsyncSessionLocal") as mock_factory,
            patch(
                "app.services.kb.extract_service.run_extraction",
                new=AsyncMock(return_value=stats),
            ) as p_run,
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await KbExtractCollector(
                {"source": "internal", "data_type": "kb_extract"}
            ).run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 5
        assert result.metadata == stats
        assert p_run.await_count == 1

    async def test_zero_work_skipped(self) -> None:
        from collector.core.base import CollectStatus
        from collector.spiders.kb_extract import KbExtractCollector

        stats = {
            "chaptersInferred": 0,
            "mediasExtracted": 0,
            "pointsCreated": 0,
            "failedMedias": 0,
        }
        with (
            patch("collector.spiders.kb_extract.AsyncSessionLocal") as mock_factory,
            patch(
                "app.services.kb.extract_service.run_extraction",
                new=AsyncMock(return_value=stats),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await KbExtractCollector(
                {"source": "internal", "data_type": "kb_extract"}
            ).run()

        assert result.status == CollectStatus.SKIPPED
        assert result.items_collected == 0
