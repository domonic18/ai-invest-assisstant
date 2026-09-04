"""校验每个已声明渠道/数据类型都有可执行任务的覆盖测试。

架构设计为每个 source 渠道分配了特定的数据类型。本模块保证
``DEFAULT_CHANNELS`` 与 ``TASK_MAP`` 保持同步：渠道声明的每个数据类型
必须映射到任务，且任务必须能为该渠道解析出采集器。
"""

from collections.abc import Awaitable, Callable
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from collector.core.base import CollectResult
from collector.runtime.channels import DEFAULT_CHANNELS
from collector.runtime.registry import TASK_MAP, TASK_SPECS


def _is_internal_task(task_name: str) -> bool:
    """内部任务不依赖外部采集渠道，不参与 channel 覆盖检查。"""
    spec = TASK_SPECS.get(task_name)
    return spec is not None and set(spec.collectors.keys()) == {"internal"}


@pytest.mark.unit
class TestCollectorCoverage:
    def test_all_channel_data_types_have_tasks(self) -> None:
        """DEFAULT_CHANNELS 中列出的每个数据类型必须存在于 TASK_MAP。"""
        channel_types = {
            data_type
            for channel in DEFAULT_CHANNELS
            for data_type in channel.get("supported_data_types", [])
        }
        missing = channel_types - set(TASK_MAP.keys())
        assert not missing, f"Channel data types without tasks: {sorted(missing)}"

    def test_all_task_names_are_channel_data_types(self) -> None:
        """每个 TASK_MAP 键应至少被一个渠道声明。

        内部任务（source=internal）不依赖外部采集渠道，允许不在 channel 中声明。
        """
        channel_types = {
            data_type
            for channel in DEFAULT_CHANNELS
            for data_type in channel.get("supported_data_types", [])
        }
        extra = set(TASK_MAP.keys()) - channel_types
        extra -= {name for name in extra if _is_internal_task(name)}
        assert not extra, f"TASK_MAP keys not declared in channels: {sorted(extra)}"

    @pytest.mark.parametrize("task_name", list(TASK_MAP.keys()))
    @pytest.mark.asyncio
    async def test_each_task_runs_with_mocked_channel(self, task_name: str) -> None:
        """每个任务都能解析出渠道并产出 CollectResult。"""
        task_coro: Callable[..., Awaitable[CollectResult]] = cast(
            Callable[..., Awaitable[CollectResult]], TASK_MAP[task_name]
        )

        with (
            patch(
                "collector.runtime.registry._resolve_task_channels",
                AsyncMock(return_value=[("mock", {"base_url": None, "api_key": None})]),
            ),
            patch(
                "collector.runtime.registry._run_collector_for_task",
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
