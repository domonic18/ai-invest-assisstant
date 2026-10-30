"""历史持仓快照重放采集器契约测试（无 agent 账户跳过/成功汇总/账户错误隔离）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.core.base import CollectStatus
from collector.spiders.paper_trade_position_replay import (
    PaperTradePositionReplayCollector,
)

_CFG = {"source": "internal", "data_type": "paper-trade-position-replay"}


def _collector() -> PaperTradePositionReplayCollector:
    return PaperTradePositionReplayCollector(_CFG)


def _session_factory(account_rows: list[SimpleNamespace]) -> MagicMock:
    def _cm():
        cm = MagicMock()
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = account_rows
        session.execute = AsyncMock(return_value=result)
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    factory = MagicMock(side_effect=lambda: _cm())
    return factory


@pytest.mark.unit
class TestPaperTradePositionReplayCollector:
    @pytest.mark.asyncio
    async def test_skips_without_agent_accounts(self) -> None:
        with patch(
            "collector.spiders.paper_trade_position_replay.AsyncSessionLocal",
            _session_factory([]),
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "Agent 账户" in (result.message or "")

    @pytest.mark.asyncio
    async def test_success_aggregates_account_summaries(self) -> None:
        accounts = [
            SimpleNamespace(id=1, agent_key="short-line"),
            SimpleNamespace(id=2, agent_key="value"),
        ]
        rebuild = AsyncMock(
            side_effect=[
                {"account_id": 1, "rows_written": 12},
                {"account_id": 2, "rows_written": 8},
            ]
        )
        with (
            patch(
                "collector.spiders.paper_trade_position_replay.AsyncSessionLocal",
                _session_factory(accounts),
            ),
            patch(
                "collector.spiders.paper_trade_position_replay.position_replay.rebuild_position_snapshots",
                rebuild,
            ),
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 20
        assert result.metadata["accounts"] == 2
        assert [d["account_id"] for d in result.metadata["details"]] == [1, 2]

    @pytest.mark.asyncio
    async def test_account_error_isolated_as_partial(self) -> None:
        accounts = [
            SimpleNamespace(id=1, agent_key="short-line"),
            SimpleNamespace(id=2, agent_key="value"),
        ]
        rebuild = AsyncMock(
            side_effect=[RuntimeError("重放失败"), {"account_id": 2, "rows_written": 3}]
        )
        with (
            patch(
                "collector.spiders.paper_trade_position_replay.AsyncSessionLocal",
                _session_factory(accounts),
            ),
            patch(
                "collector.spiders.paper_trade_position_replay.position_replay.rebuild_position_snapshots",
                rebuild,
            ),
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.PARTIAL
        assert any("short-line" in err for err in result.errors)
        assert result.items_stored == 3
