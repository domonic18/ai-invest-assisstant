"""资讯 AI 重要度分级服务单测。"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.news import NewsScoreBatch, NewsScoreItem
from app.services.news import news_score_service
from app.services.news.news_score_service import score_pending

_NOW = datetime(2026, 9, 8, 6, 0, tzinfo=timezone.utc)


def _tg_row(msg_id: int, content: str = "内容") -> MagicMock:
    row = MagicMock()
    row.cls_msg_id = msg_id
    row.title = f"标题{msg_id}"
    row.content = content
    row.category = "重点"
    row.stock_codes = ["600519"]
    return row


def _patch_lock(acquired: bool):
    """替换 redis_lock 为立返 acquired 的假锁。"""

    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield acquired

    return patch(
        "app.services.news.news_score_service.redis_lock",
        side_effect=fake_lock,
    )


@pytest.mark.unit
class TestScorePending:
    async def test_lock_busy_returns_zero(self) -> None:
        with _patch_lock(False):
            result = await score_pending(MagicMock())
        assert result == {"scored": 0, "by_source": {}}

    async def test_scores_batches_and_commits(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        batcher = AsyncMock(
            side_effect=[
                [
                    news_score_service._telegraph_payload(_tg_row(101)),
                    news_score_service._telegraph_payload(_tg_row(102)),
                ],
                [],  # 第二批后无待评
            ]
        )
        output = NewsScoreBatch(
            items=[
                NewsScoreItem(source="cls_telegraph", item_id="101", score=85, reason="央行降准"),
                NewsScoreItem(source="cls_telegraph", item_id="102", score=30, reason="日常播报"),
            ]
        )
        with (
            _patch_lock(True),
            patch.object(
                news_score_service.ai_score_repository,
                "upsert_scores",
                AsyncMock(return_value=2),
            ) as mock_upsert,
            patch(
                "app.agent.runtime.structured.run_structured",
                AsyncMock(return_value=output),
            ),
        ):
            # 只注册临时源，避免真实 telegraph batcher 也跑
            with patch.dict(
                news_score_service._SOURCE_BATCHERS, {"cls_telegraph": batcher}
            ):
                result = await score_pending(session)

        assert result["scored"] == 2
        assert result["by_source"] == {"cls_telegraph": 2}
        # 一批一次批量 upsert；第二批为空直接停
        assert mock_upsert.await_count == 1
        assert session.commit.await_count == 1

    async def test_llm_failure_skips_batch_no_write(self) -> None:
        session = MagicMock()
        batcher = AsyncMock(
            return_value=[news_score_service._telegraph_payload(_tg_row(201))]
        )
        with (
            _patch_lock(True),
            patch.object(
                news_score_service.ai_score_repository,
                "upsert_scores",
                AsyncMock(),
            ) as mock_upsert,
            patch(
                "app.agent.runtime.structured.run_structured",
                AsyncMock(side_effect=ValueError("LLM 输出不符 schema")),
            ),
            patch.dict(news_score_service._SOURCE_BATCHERS, {"cls_telegraph": batcher}),
        ):
            result = await score_pending(session)

        assert result["scored"] == 0
        mock_upsert.assert_not_awaited()

    async def test_hallucinated_items_filtered(self) -> None:
        session = MagicMock()
        batch = [news_score_service._telegraph_payload(_tg_row(301))]
        output = NewsScoreBatch(
            items=[
                NewsScoreItem(source="cls_telegraph", item_id="301", score=50, reason="ok"),
                NewsScoreItem(source="cls_telegraph", item_id="999", score=99, reason="幻觉"),
                NewsScoreItem(source="sina_news", item_id="301", score=99, reason="串源"),
            ]
        )
        prompt_config = MagicMock()
        prompt_config.user_prompt_template = "评 {count} 条：{items_json}"
        with patch(
            "app.agent.runtime.structured.run_structured",
            AsyncMock(return_value=output),
        ):
            rows = await news_score_service._score_batch(session, prompt_config, batch)
        assert len(rows) == 1
        assert rows[0]["item_id"] == "301"
        assert rows[0]["score_detail"] == {"reason": "ok"}


@pytest.mark.unit
class TestPayload:
    def test_content_truncated(self) -> None:
        row = _tg_row(1, content="长" * 600)
        payload = news_score_service._telegraph_payload(row)
        assert len(payload["content"]) == news_score_service._CONTENT_CHARS
        assert payload["item_id"] == "1"
        assert payload["source"] == "cls_telegraph"
        assert payload["stock_codes"] == ["600519"]

    async def test_second_source_registered_included(self) -> None:
        """新源注册进 _SOURCE_BATCHERS 后自动纳入评分循环。"""
        session = MagicMock()
        session.commit = AsyncMock()
        telegraph_batcher = AsyncMock(return_value=[])
        extra_batcher = AsyncMock(
            side_effect=[
                [{"source": "x_video", "item_id": "v1", "title": "t", "content": "c",
                  "category": None, "stock_codes": []}],
                [],
            ]
        )
        output = NewsScoreBatch(
            items=[NewsScoreItem(source="x_video", item_id="v1", score=88, reason="权威博主")]
        )
        with (
            _patch_lock(True),
            patch.object(
                news_score_service.ai_score_repository,
                "upsert_scores",
                AsyncMock(return_value=1),
            ),
            patch(
                "app.agent.runtime.structured.run_structured",
                AsyncMock(return_value=output),
            ),
            patch.dict(
                news_score_service._SOURCE_BATCHERS,
                {"cls_telegraph": telegraph_batcher, "x_video": extra_batcher},
            ),
        ):
            result = await score_pending(session)

        assert result["by_source"] == {"x_video": 1}
        telegraph_batcher.assert_awaited_once()


@pytest.mark.unit
class TestNewsAiScoreCollector:
    async def test_run_success_and_skipped(self) -> None:
        from collector.spiders.news_ai_score import NewsAiScoreCollector

        collector = NewsAiScoreCollector(config={})
        with patch(
            "app.services.news.news_score_service.score_pending",
            AsyncMock(return_value={"scored": 3, "by_source": {"cls_telegraph": 3}}),
        ):
            result = await collector.run()
        assert result.status.value == "success"
        assert result.items_stored == 3

        with patch(
            "app.services.news.news_score_service.score_pending",
            AsyncMock(return_value={"scored": 0, "by_source": {}}),
        ):
            result = await collector.run()
        assert result.status.value == "skipped"

    async def test_run_failure(self) -> None:
        from collector.spiders.news_ai_score import NewsAiScoreCollector

        collector = NewsAiScoreCollector(config={})
        with patch(
            "app.services.news.news_score_service.score_pending",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            result = await collector.run()
        assert result.status.value == "failed"
