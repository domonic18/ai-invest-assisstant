"""产业链定时刷新采集器测试。"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services.chain import chain_refresh_service
from collector.core.base import CollectStatus
from collector.spiders.chain_refresh import ChainRefreshCollector


def _collector() -> ChainRefreshCollector:
    return ChainRefreshCollector(
        {"source": "internal", "data_type": "ai_chain_refresh"}
    )


@pytest.mark.unit
class TestChainRefreshRun:
    async def test_skips_without_targets(self) -> None:
        with patch.object(
            chain_refresh_service,
            "list_refresh_targets",
            new=AsyncMock(return_value=[]),
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "没有可刷新的产业链" in (result.errors or [""])[0]

    async def test_generates_per_target_and_counts(self) -> None:
        targets = [("半导体", [3]), ("机器人", [3, 5])]
        with (
            patch.object(
                chain_refresh_service,
                "list_refresh_targets",
                new=AsyncMock(return_value=targets),
            ),
            patch.object(
                chain_refresh_service,
                "refresh_industry",
                new=AsyncMock(side_effect=[2, 2]),
            ) as mock_refresh,
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["generated"] == 2
        assert result.metadata["industries"]["半导体"] == "generated:2"
        assert result.metadata["industries"]["机器人"] == "generated:2"
        first_call = mock_refresh.await_args_list[0]
        assert first_call.args[1] == "半导体"
        assert isinstance(first_call.kwargs["signal_date"], date)

    async def test_isolates_single_industry_failure(self) -> None:
        targets = [("半导体", [3]), ("机器人", [3])]
        with (
            patch.object(
                chain_refresh_service,
                "list_refresh_targets",
                new=AsyncMock(return_value=targets),
            ),
            patch.object(
                chain_refresh_service,
                "refresh_industry",
                new=AsyncMock(side_effect=[RuntimeError("llm timeout"), 2]),
            ),
            patch(
                "collector.spiders.chain_refresh.AsyncSessionLocal"
            ) as mock_factory,
        ):
            session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = session
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["generated"] == 1
        assert result.metadata["failed"] == 1
        assert result.metadata["industries"]["半导体"].startswith("failed:")
        assert result.metadata["industries"]["机器人"] == "generated:2"
        session.rollback.assert_awaited_once()

    async def test_all_failed_is_failure(self) -> None:
        with (
            patch.object(
                chain_refresh_service,
                "list_refresh_targets",
                new=AsyncMock(return_value=[("半导体", [3])]),
            ),
            patch.object(
                chain_refresh_service,
                "refresh_industry",
                new=AsyncMock(side_effect=RuntimeError("llm timeout")),
            ),
            patch(
                "collector.spiders.chain_refresh.AsyncSessionLocal"
            ) as mock_factory,
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert result.metadata["failed"] == 1
