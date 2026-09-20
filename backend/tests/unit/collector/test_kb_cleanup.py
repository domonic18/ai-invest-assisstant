"""知识库物理清理采集器测试（internal 薄壳委托 cleanup_service）。"""

from unittest.mock import AsyncMock, patch

import pytest

from collector.core.base import CollectStatus
from collector.spiders.kb_cleanup import KbCleanupCollector


def _collector() -> KbCleanupCollector:
    return KbCleanupCollector({"source": "internal", "data_type": "kb_cleanup"})


@pytest.mark.unit
class TestKbCleanupRun:
    async def test_purged_reports_success(self) -> None:
        stats = {
            "purgedMedia": 2,
            "purgedSources": 1,
            "purgedBytes": 500,
            "abortedSessions": 1,
            "orphanObjects": 0,
            "orphanBytes": 0,
        }
        with (
            patch(
                "collector.spiders.kb_cleanup.AsyncSessionLocal"
            ) as mock_factory,
            patch(
                "collector.spiders.kb_cleanup.cleanup_service.run_cleanup",
                new=AsyncMock(return_value=stats),
            ) as p_cleanup,
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 3
        assert result.metadata == stats
        assert p_cleanup.call_args.kwargs["deep"] is True

    async def test_no_backlog_is_benign_skipped(self) -> None:
        stats = {
            "purgedMedia": 0,
            "purgedSources": 0,
            "purgedBytes": 0,
            "abortedSessions": 0,
            "orphanObjects": 0,
            "orphanBytes": 0,
        }
        with (
            patch(
                "collector.spiders.kb_cleanup.AsyncSessionLocal"
            ) as mock_factory,
            patch(
                "collector.spiders.kb_cleanup.cleanup_service.run_cleanup",
                new=AsyncMock(return_value=stats),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "无可清理积压" in (result.message or "")

    async def test_busy_lock_is_skipped(self) -> None:
        with (
            patch(
                "collector.spiders.kb_cleanup.AsyncSessionLocal"
            ) as mock_factory,
            patch(
                "collector.spiders.kb_cleanup.cleanup_service.run_cleanup",
                new=AsyncMock(return_value={"skippedBusy": 1}),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED

    async def test_failure_propagates_as_failed_result(self) -> None:
        with (
            patch(
                "collector.spiders.kb_cleanup.AsyncSessionLocal"
            ) as mock_factory,
            patch(
                "collector.spiders.kb_cleanup.cleanup_service.run_cleanup",
                new=AsyncMock(side_effect=RuntimeError("db down")),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert "db down" in (result.errors or [""])[0]
