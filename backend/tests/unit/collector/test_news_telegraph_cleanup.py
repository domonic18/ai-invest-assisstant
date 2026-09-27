"""电报保留清理器测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.core.base import CollectStatus
from collector.spiders.news_telegraph_cleanup import NewsTelegraphCleanupCollector


def _collector() -> NewsTelegraphCleanupCollector:
    return NewsTelegraphCleanupCollector(
        {"source": "internal", "data_type": "news_telegraph_cleanup"}
    )


def _execute_result(rowcount: int) -> MagicMock:
    result = MagicMock()
    result.rowcount = rowcount
    return result


@pytest.mark.unit
class TestNewsTelegraphCleanupRun:
    async def test_deletes_scores_then_telegraphs_and_reports_counts(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _execute_result(7),   # news_ai_score 孤儿标注
            _execute_result(45),  # news_telegraph 本体
        ]

        with patch(
            "collector.spiders.news_telegraph_cleanup.AsyncSessionLocal"
        ) as mock_factory:
            mock_factory.return_value.__aenter__.return_value = session
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["deleted_telegraphs"] == 45
        assert result.metadata["deleted_scores"] == 7
        assert result.metadata["retention_days"] == 180
        assert result.items_stored == 45
        # 先删孤儿标注再删电报本体（同一事务）
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    async def test_retention_days_kwarg_overrides_default(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [_execute_result(0), _execute_result(3)]

        with patch(
            "collector.spiders.news_telegraph_cleanup.AsyncSessionLocal"
        ) as mock_factory:
            mock_factory.return_value.__aenter__.return_value = session
            result = await _collector().run(retention_days=1)

        assert result.metadata["retention_days"] == 1
        assert result.metadata["deleted_telegraphs"] == 3

    async def test_failure_propagates_as_failed_result(self) -> None:
        with patch(
            "collector.spiders.news_telegraph_cleanup.AsyncSessionLocal"
        ) as mock_factory:
            session = AsyncMock()
            session.execute.side_effect = RuntimeError("db down")
            mock_factory.return_value.__aenter__.return_value = session
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert "db down" in (result.errors or [""])[0]
