"""agent 行情/日历工具单测（mock service，不触网不连库）。"""


from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools import (
    get_trade_calendar,
)
from app.agent.tools import market_tools as mt
from app.schemas.market import (
    CollectTaskResult,
)


@pytest.mark.unit
class TestTradeCalendarTool:
    @pytest.mark.asyncio
    async def test_returns_now_today_and_trading_days(self) -> None:
        with (
            patch("app.agent.tools.market_tools.now_cn") as mock_now,
            patch.object(
                mt.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 4)),
            ),
            patch.object(
                mt.trade_calendar_service,
                "is_trading_day",
                AsyncMock(return_value=False),
            ),
        ):
            result = await get_trade_calendar.ainvoke({})

        assert result["today"] == mock_now.return_value.date().isoformat()
        assert result["latest_trading_day"] == "2026-09-04"
        assert result["today_is_trading_day"] is False
        assert "now" in result


@pytest.mark.unit
class TestCollectMarketDataTool:
    @pytest.mark.asyncio
    async def test_dispatches_and_reports_note(self) -> None:
        results = [
            CollectTaskResult(
                task="sector-fund-flow", status="dispatched", items_collected=0
            ),
            CollectTaskResult(
                task="index-kline", status="dispatched", items_collected=0
            ),
        ]
        with patch(
            "app.services.collector.market_dispatch_service.collect_market_data",
            AsyncMock(return_value=results),
        ) as m:
            result = await mt.collect_market_data.ainvoke(
                {"trade_date": "2026-09-04"}
            )

        assert m.await_args.args[1] == date(2026, 9, 4)
        assert m.await_args.args[2] is None
        assert result["trade_date"] == "2026-09-04"
        assert result["dispatched"] == ["sector-fund-flow", "index-kline"]
        assert "板块资金流" in result["note"]

    @pytest.mark.asyncio
    async def test_symbols_forwarded(self) -> None:
        with patch(
            "app.services.collector.market_dispatch_service.collect_market_data",
            AsyncMock(return_value=[]),
        ) as m:
            await mt.collect_market_data.ainvoke(
                {"trade_date": "2026-09-04", "symbols": ["000001", "600519"]}
            )
        assert m.await_args.args[2] == ["000001", "600519"]

    @pytest.mark.asyncio
    async def test_non_trading_day_returns_error(self) -> None:
        from app.services.collector import market_dispatch_service

        with patch(
            "app.services.collector.market_dispatch_service.collect_market_data",
            AsyncMock(
                side_effect=market_dispatch_service.NonTradingDayError(
                    "2026-09-06 不是交易日，无法补采数据"
                )
            ),
        ):
            result = await mt.collect_market_data.ainvoke(
                {"trade_date": "2026-09-06"}
            )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejects_bad_trade_date(self) -> None:
        result = await mt.collect_market_data.ainvoke({"trade_date": "2026/09/04"})
        assert result == {"error": "trade_date 须为 YYYY-MM-DD 格式"}
