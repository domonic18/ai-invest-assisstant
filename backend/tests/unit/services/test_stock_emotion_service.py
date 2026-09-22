"""个股情绪面上下文服务测试（mock 数据源，不连库）。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market.stock_emotion_service import build_stock_emotion_context

_TRADE_DATE = date(2026, 9, 22)
_PREV_DATE = date(2026, 9, 21)

_STOCK = SimpleNamespace(industry_level_2="燃气", industry_level_1="公用事业")


def _flow_row(trade_date: date, sector_name: str, main_net_inflow: float):
    return SimpleNamespace(
        trade_date=trade_date,
        sector_name=sector_name,
        main_net_inflow=main_net_inflow,
    )


def _pool_item(stock_code: str, industry: str = "燃气", boards: int = 1):
    return SimpleNamespace(
        stock_code=stock_code,
        consecutive_boards=boards,
        first_seal_time="09:35:00",
        last_seal_time="14:55:00",
        broken_limit_count=0,
        limit_status="封板",
        seal_type=None,
        industry=industry,
    )


def _pool_response(items):
    return SimpleNamespace(
        total=len(items),
        first_board=sum(1 for i in items if (i.consecutive_boards or 1) == 1),
        continuous=sum(1 for i in items if (i.consecutive_boards or 1) >= 2),
        max_boards=max((i.consecutive_boards or 1) for i in items) if items else None,
        items=items,
    )


def _patch_sources(
    stock=None,
    sector_rows=None,
    fund_rows=None,
    pool_items=None,
):
    return (
        patch(
            "app.services.market.stock_service.get_stock_by_code",
            AsyncMock(return_value=stock),
        ),
        patch(
            "app.repositories.market.sector_fund_flow_repository.list_recent",
            AsyncMock(return_value=sector_rows or []),
        ),
        patch(
            "app.repositories.market.fund_flow_repository.list_paginated",
            AsyncMock(return_value=(fund_rows or [], 0)),
        ),
        patch(
            "app.services.market.limit_pool_service.get_limit_up",
            AsyncMock(return_value=_pool_response(pool_items or [])),
        ),
    )


@pytest.mark.unit
class TestBuildStockEmotionContext:
    @pytest.mark.asyncio
    async def test_full_context_when_all_sources_hit(self) -> None:
        """行业资金/排名/累计、个股资金、连板状态、行业涨停数、市场结构齐全。"""
        patches = _patch_sources(
            stock=_STOCK,
            sector_rows=[
                _flow_row(_TRADE_DATE, "银行", 10e8),
                _flow_row(_TRADE_DATE, "燃气", 5e8),
                _flow_row(_TRADE_DATE, "医药", -3e8),
                _flow_row(_PREV_DATE, "燃气", 2e8),
                _flow_row(_PREV_DATE, "银行", 1e8),
            ],
            fund_rows=[
                SimpleNamespace(trade_date=_PREV_DATE, main_net_inflow=1e8),
                SimpleNamespace(trade_date=_TRADE_DATE, main_net_inflow=-0.5e8),
            ],
            pool_items=[
                _pool_item("002259", boards=2),
                _pool_item("000592", boards=1),
                _pool_item("600000", industry="银行", boards=3),
            ],
        )
        with patches[0], patches[1], patches[2], patches[3]:
            ctx = await build_stock_emotion_context(MagicMock(), "002259", _TRADE_DATE)

        assert ctx["industry"] == "燃气"
        flow = ctx["industry_flow"]
        assert flow["latest_trade_date"] == _TRADE_DATE.isoformat()
        assert flow["latest_net_inflow_yi"] == 5.0
        assert flow["rank"] == 2
        assert flow["industries_total"] == 3
        assert flow["recent_5d_net_yi"] == 7.0
        assert ctx["stock_flow"]["items"] == [
            {"trade_date": _PREV_DATE.isoformat(), "main_net_inflow_yi": 1.0},
            {"trade_date": _TRADE_DATE.isoformat(), "main_net_inflow_yi": -0.5},
        ]
        assert ctx["stock_limit_up"]["consecutive_boards"] == 2
        assert ctx["stock_limit_up"]["first_seal_time"] == "09:35:00"
        assert ctx["industry_limit_up_count"] == 2
        assert ctx["market_emotion"] == {
            "total": 3,
            "first_board": 1,
            "continuous": 2,
            "max_boards": 3,
        }

    @pytest.mark.asyncio
    async def test_stock_not_in_pool_yields_null_limit_up(self) -> None:
        patches = _patch_sources(
            stock=_STOCK,
            pool_items=[_pool_item("600000", industry="银行", boards=1)],
        )
        with patches[0], patches[1], patches[2], patches[3]:
            ctx = await build_stock_emotion_context(MagicMock(), "002259", _TRADE_DATE)

        assert ctx["stock_limit_up"] is None

    @pytest.mark.asyncio
    async def test_industry_mismatch_yields_null_flow_and_count(self) -> None:
        """行业名在资金流/涨停池中不存在时置 null，不硬凑。"""
        patches = _patch_sources(
            stock=SimpleNamespace(industry_level_2="燃气", industry_level_1=None),
            sector_rows=[
                _flow_row(_TRADE_DATE, "银行", 10e8),
                _flow_row(_TRADE_DATE, "医药", -3e8),
            ],
            pool_items=[_pool_item("600000", industry="银行", boards=1)],
        )
        with patches[0], patches[1], patches[2], patches[3]:
            ctx = await build_stock_emotion_context(MagicMock(), "002259", _TRADE_DATE)

        assert ctx["industry"] == "燃气"
        assert ctx["industry_flow"] is None
        assert ctx["industry_limit_up_count"] == 0

    @pytest.mark.asyncio
    async def test_missing_stock_and_empty_pool(self) -> None:
        """股票无基础信息且涨停池为空：industry 归 null，市场结构为 null。"""
        patches = _patch_sources(stock=None)
        with patches[0], patches[1], patches[2], patches[3]:
            ctx = await build_stock_emotion_context(MagicMock(), "002259", _TRADE_DATE)

        assert ctx["industry"] is None
        assert ctx["industry_flow"] is None
        assert ctx["industry_limit_up_count"] is None
        assert ctx["market_emotion"] is None
        assert ctx["stock_limit_up"] is None

    @pytest.mark.asyncio
    async def test_industry_falls_back_to_level1(self) -> None:
        patches = _patch_sources(
            stock=SimpleNamespace(industry_level_2=None, industry_level_1="公用事业"),
        )
        with patches[0], patches[1], patches[2], patches[3]:
            ctx = await build_stock_emotion_context(MagicMock(), "002259", _TRADE_DATE)

        assert ctx["industry"] == "公用事业"
