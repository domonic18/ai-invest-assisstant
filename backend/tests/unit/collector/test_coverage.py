"""Verification tests that every declared channel/data-type has a runnable task.

The architecture design assigns specific data types to each source channel.  This
module ensures that ``DEFAULT_CHANNELS`` and ``TASK_MAP`` stay in sync: every
data type declared in a channel must map to a task, and the task must be able to
resolve a collector for that channel.
"""

from collections.abc import Awaitable, Callable
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from collector.base import CollectResult
from collector.channels import DEFAULT_CHANNELS
from collector.tasks import TASK_MAP


@pytest.mark.unit
class TestCollectorCoverage:
    def test_all_channel_data_types_have_tasks(self) -> None:
        """Every data type listed in DEFAULT_CHANNELS must exist in TASK_MAP."""
        channel_types = {
            data_type
            for channel in DEFAULT_CHANNELS
            for data_type in channel.get("supported_data_types", [])
        }
        missing = channel_types - set(TASK_MAP.keys())
        assert not missing, f"Channel data types without tasks: {sorted(missing)}"

    def test_all_task_names_are_channel_data_types(self) -> None:
        """Every TASK_MAP key should be declared by at least one channel."""
        channel_types = {
            data_type
            for channel in DEFAULT_CHANNELS
            for data_type in channel.get("supported_data_types", [])
        }
        extra = set(TASK_MAP.keys()) - channel_types
        assert not extra, f"TASK_MAP keys not declared in channels: {sorted(extra)}"

    @pytest.mark.parametrize("task_name", list(TASK_MAP.keys()))
    @pytest.mark.asyncio
    async def test_each_task_runs_with_mocked_channel(self, task_name: str) -> None:
        """Each task can resolve a channel and produce a CollectResult."""
        task_coro: Callable[..., Awaitable[CollectResult]] = cast(
            Callable[..., Awaitable[CollectResult]], TASK_MAP[task_name]
        )

        with (
            patch(
                "collector.tasks._resolve_task_channel",
                AsyncMock(return_value=("mock", {"base_url": None, "api_key": None})),
            ),
            patch(
                "collector.tasks._run_collector_for_task",
                AsyncMock(
                    return_value=AsyncMock(
                        status=AsyncMock(value="success"),
                        items_collected=1,
                        items_stored=1,
                        errors=[],
                    )
                ),
            ) as mock_run,
        ):
            if task_name == "kline":
                result = await task_coro(period="daily")
            elif task_name == "sector-fund-flow":
                result = await task_coro(sector_type="industry")
            elif task_name == "financial-report":
                result = await task_coro(report_types=["年报"])
            elif task_name == "fund-holdings":
                result = await task_coro(report_date="2024-03-31")
            elif task_name == "macro":
                result = await task_coro(indicators=["cpi"])
            else:
                result = await task_coro()

        assert result.status.value == "success"
        mock_run.assert_awaited_once()
