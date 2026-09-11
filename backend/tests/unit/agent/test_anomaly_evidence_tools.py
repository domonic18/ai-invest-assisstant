"""异动归因证据工具单测（龙虎榜 / 个股资金流，mock 仓储不连库）。"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools.dragon_tiger_tools import get_dragon_tiger
from app.agent.tools.stock_tools import get_stock_fund_flow

_END_DATE = date(2026, 9, 10)


def _session_factory() -> MagicMock:
    factory = MagicMock()
    session = AsyncMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


def _dt_row(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "trade_date": _END_DATE,
        "stock_code": "000001",
        "stock_name": "平安银行",
        "rank_reason": "日涨幅偏离值达7%",
        "close_price": Decimal("12.340"),
        "change_pct": Decimal("7.10"),
        "net_buy_amount": Decimal("150000000"),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _flow_row(trade_date: date, main: str) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=trade_date,
        main_net_inflow=Decimal(main),
        super_large_net=Decimal(main),
        large_net=None,
        medium_net=None,
        small_net=None,
    )


@pytest.mark.unit
class TestGetDragonTiger:
    @pytest.mark.asyncio
    async def test_stock_mode_returns_recent_records(self) -> None:
        rows = [
            _dt_row(),
            _dt_row(trade_date=date(2026, 9, 5), rank_reason="换手率达20%"),
        ]
        with (
            patch(
                "app.agent.tools.dragon_tiger_tools.AsyncSessionLocal",
                _session_factory(),
            ),
            patch(
                "app.repositories.market.dragon_tiger_repository.list_by_stock",
                AsyncMock(return_value=rows),
            ) as mock_list,
            patch(
                "app.services.market.trade_calendar_service"
                ".resolve_latest_trade_date",
                AsyncMock(return_value=_END_DATE),
            ),
        ):
            result = await get_dragon_tiger.ainvoke({"stock_code": "000001"})

        assert result["stock_code"] == "000001"
        assert result["window_end"] == "2026-09-10"
        assert len(result["items"]) == 2
        first = result["items"][0]
        assert first["rank_reason"] == "日涨幅偏离值达7%"
        assert first["net_buy_amount_yi"] == 1.5
        assert first["close_price"] == 12.34
        mock_list.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_board_mode_defaults_to_latest_trade_date(self) -> None:
        rows = [_dt_row()]
        with (
            patch(
                "app.agent.tools.dragon_tiger_tools.AsyncSessionLocal",
                _session_factory(),
            ),
            patch(
                "app.repositories.market.dragon_tiger_repository.list_by_date",
                AsyncMock(return_value=rows),
            ) as mock_list,
            patch(
                "app.services.market.trade_calendar_service"
                ".resolve_latest_trade_date",
                AsyncMock(return_value=_END_DATE),
            ),
        ):
            result = await get_dragon_tiger.ainvoke({})

        assert result["trade_date"] == "2026-09-10"
        assert result["total"] == 1
        assert result["items"][0]["stock_code"] == "000001"
        assert mock_list.await_args is not None
        assert mock_list.await_args.args[1] == _END_DATE

    @pytest.mark.asyncio
    async def test_invalid_trade_date_returns_error(self) -> None:
        result = await get_dragon_tiger.ainvoke({"trade_date": "2026/09/01"})
        assert "error" in result


@pytest.mark.unit
class TestGetStockFundFlow:
    @pytest.mark.asyncio
    async def test_converts_to_yi_and_orders_by_date(self) -> None:
        rows = [
            _flow_row(date(2026, 9, 8), "120000000"),
            _flow_row(date(2026, 9, 9), "-50000000"),
            _flow_row(date(2026, 9, 10), "80000000"),
        ]
        with (
            patch(
                "app.agent.tools.stock_tools.AsyncSessionLocal",
                _session_factory(),
            ),
            patch(
                "app.repositories.market.fund_flow_repository.list_paginated",
                AsyncMock(return_value=(rows, len(rows))),
            ) as mock_list,
        ):
            result = await get_stock_fund_flow.ainvoke(
                {"stock_code": "000001", "days": 5}
            )

        assert result["unit"] == "亿元（净流入为正）"
        assert [item["trade_date"] for item in result["items"]] == [
            "2026-09-08",
            "2026-09-09",
            "2026-09-10",
        ]
        assert result["items"][0]["main_net_inflow_yi"] == 1.2
        assert result["items"][1]["main_net_inflow_yi"] == -0.5
        assert result["items"][0]["super_large_net_yi"] == 1.2
        assert result["items"][0]["large_net_yi"] is None
        assert mock_list.await_args is not None
        assert mock_list.await_args.kwargs["stock_code"] == "000001"

    @pytest.mark.asyncio
    async def test_clamps_days_to_upper_bound(self) -> None:
        with (
            patch(
                "app.agent.tools.stock_tools.AsyncSessionLocal",
                _session_factory(),
            ),
            patch(
                "app.repositories.market.fund_flow_repository.list_paginated",
                AsyncMock(return_value=([], 0)),
            ) as mock_list,
        ):
            await get_stock_fund_flow.ainvoke({"stock_code": "000001", "days": 999})

        assert mock_list.await_args is not None
        kwargs = mock_list.await_args.kwargs
        assert (kwargs["end_date"] - kwargs["start_date"]).days == 30 * 2
