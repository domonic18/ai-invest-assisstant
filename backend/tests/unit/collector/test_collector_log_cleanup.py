"""采集日志保留清理器测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.core.base import CollectStatus
from collector.spiders.collector_log_cleanup import CollectorLogCleanupCollector


def _collector() -> CollectorLogCleanupCollector:
    return CollectorLogCleanupCollector(
        {"source": "internal", "data_type": "system_maintenance"}
    )


@pytest.mark.unit
class TestCollectorLogCleanupRun:
    async def test_deletes_and_reports_count(self) -> None:
        session = AsyncMock()
        execute_result = MagicMock()
        execute_result.rowcount = 123
        session.execute.return_value = execute_result

        with patch(
            "collector.spiders.collector_log_cleanup.AsyncSessionLocal"
        ) as mock_factory:
            mock_factory.return_value.__aenter__.return_value = session
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["deleted"] == 123
        assert result.metadata["retention_days"] == 90
        session.commit.assert_awaited_once()

    async def test_zero_rowcount_is_success(self) -> None:
        session = AsyncMock()
        execute_result = MagicMock()
        execute_result.rowcount = 0
        session.execute.return_value = execute_result

        with patch(
            "collector.spiders.collector_log_cleanup.AsyncSessionLocal"
        ) as mock_factory:
            mock_factory.return_value.__aenter__.return_value = session
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["deleted"] == 0

    async def test_failure_propagates_as_failed_result(self) -> None:
        with patch(
            "collector.spiders.collector_log_cleanup.AsyncSessionLocal"
        ) as mock_factory:
            session = AsyncMock()
            session.execute.side_effect = RuntimeError("db down")
            mock_factory.return_value.__aenter__.return_value = session
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert "db down" in (result.errors or [""])[0]
