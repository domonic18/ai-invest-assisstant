"""assistant_tools 工具层单测（mock service，不触网不连库）。"""

from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.runtime import assistant_tools as at
from app.schemas.capital_fund_flow_sector import (
    SectorFlowSeries,
    SectorFlowTrendResponse,
)
from app.schemas.chain import ChainAnalyzeResponse
from app.schemas.market import IndexQuoteResponse, MarketStatsResponse
from app.schemas.stock import IndexAuctionSeries, IndexAuctionTrendResponse


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


@pytest.fixture(autouse=True)
def no_db(monkeypatch):
    monkeypatch.setattr(at, "AsyncSessionLocal", lambda: _fake_session())


@pytest.mark.unit
class TestBuildAssistantTools:
    def test_returns_ten_tools(self) -> None:
        tools = at.build_assistant_tools()
        names = [t.name for t in tools]
        assert names == [
            "get_stock_quote",
            "get_stock_kline",
            "query_financial_data",
            "search_news",
            "search_vector_kb",
            "get_sector_fund_flow",
            "get_market_overview",
            "get_auction_summary",
            "query_industry_companies",
            "persist_chain_analysis",
        ]


@pytest.mark.unit
class TestClamping:
    @pytest.mark.asyncio
    async def test_stock_kline_limit_clamped(self) -> None:
        with patch.object(
            at.db_tools, "query_stock_kline", AsyncMock(return_value=[])
        ) as mock_query:
            await at.get_stock_kline.ainvoke({"stock_code": "000001", "limit": 500})
        assert mock_query.call_args.args[2] == at.KLINE_MAX_DAYS

    @pytest.mark.asyncio
    async def test_financial_codes_and_periods_capped(self) -> None:
        codes = [f"{i:06d}" for i in range(7)]
        with patch.object(
            at.db_tools, "query_financial_data", AsyncMock(return_value=[])
        ) as mock_query:
            await at.query_financial_data.ainvoke(
                {"stock_codes": codes, "periods": 99}
            )
        args = mock_query.call_args.args
        assert args[1] == codes[: at.FINANCIAL_MAX_CODES]
        assert args[2] == at.FINANCIAL_MAX_PERIODS

    @pytest.mark.asyncio
    async def test_news_days_and_limit_clamped(self) -> None:
        with patch.object(at.db_tools, "search_news", AsyncMock(return_value=[])) as m:
            await at.search_news.ainvoke({"keyword": "半导体", "days": 999, "limit": 99})
        assert m.call_args.args[2:] == (at.NEWS_MAX_DAYS, at.NEWS_MAX_ROWS, None)

    @pytest.mark.asyncio
    async def test_vector_kb_limit_clamped(self) -> None:
        with patch.object(
            at.db_tools, "search_vector_kb", AsyncMock(return_value=[])
        ) as m:
            await at.search_vector_kb.ainvoke({"query": "光模块", "limit": 99})
        assert m.call_args.args[2] == at.KB_MAX_ROWS


@pytest.mark.unit
class TestIndustryChainTools:
    @pytest.mark.asyncio
    async def test_query_industry_companies_limit_clamped(self) -> None:
        payload = [{"code": "000001", "name": "平安银行"}]
        with patch.object(
            at.db_tools, "query_industry_companies", AsyncMock(return_value=payload)
        ) as m:
            result = await at.query_industry_companies.ainvoke(
                {"industry": "银行", "limit": 500}
            )
        assert m.call_args.args[2] == at.INDUSTRY_COMPANIES_MAX_LIMIT
        assert result == payload

    @pytest.mark.asyncio
    async def test_persist_chain_analysis_emits_event(self) -> None:
        result_payload = {
            "nodes": [
                {
                    "name": "设计",
                    "type": "upstream",
                    "companies": [{"code": "000001", "name": "A"}],
                }
            ],
            "edges": [
                {
                    "source": "设计",
                    "target": "制造",
                    "relation": "供应",
                    "strength": 0.8,
                }
            ],
            "summary": "测试",
        }
        version = ChainAnalyzeResponse(
            version_id=123, version_no=5, status="success"
        )
        with patch(
            "app.services.chain_service.persist_analysis_result",
            AsyncMock(return_value=version),
        ) as m:
            result = await at.persist_chain_analysis.ainvoke(
                {"industry": "半导体", "result": result_payload}
            )
        m.assert_awaited_once()
        assert result["version_id"] == 123
        assert result["version_no"] == 5
        assert result["__event__"]["type"] == "industry_chain.analysis_complete"


@pytest.mark.unit
class TestOutputShaping:
    @pytest.mark.asyncio
    async def test_stock_quote_passthrough(self) -> None:
        payload = {"code": "000001", "price": 11.4}
        with patch.object(
            at.stock_service, "get_stock_quote", AsyncMock(return_value=payload)
        ):
            result = await at.get_stock_quote.ainvoke({"stock_code": "000001"})
        assert result == payload

    @pytest.mark.asyncio
    async def test_sector_flow_trims_to_top_n(self) -> None:
        response = SectorFlowTrendResponse(
            dates=[date(2026, 8, 20), date(2026, 8, 21), date(2026, 8, 22)],
            sectors=[
                SectorFlowSeries(code="BK1", name="半导体", values=[10.0, -2.0, None]),
                SectorFlowSeries(code="BK2", name="银行", values=[1.0, 1.0, 1.0]),
                SectorFlowSeries(code="BK3", name="白酒", values=[-50.0, None, None]),
            ],
        )
        with patch.object(
            at.sector_fund_flow_service,
            "get_sector_flow_trend",
            AsyncMock(return_value=response),
        ):
            result = await at.get_sector_fund_flow.ainvoke({"days": 3, "top": 2})

        assert result["dates"] == ["2026-08-20", "2026-08-22"]
        names = [s["name"] for s in result["sectors"]]
        assert names == ["白酒", "半导体"]
        assert result["sectors"][0]["period_net_inflow_yi"] == -50.0
        assert result["sectors"][1]["latest_yi"] == -2.0

    @pytest.mark.asyncio
    async def test_market_overview_drops_trend_and_serializes_dates(self) -> None:
        stats = MarketStatsResponse(trade_date=date(2026, 8, 21), up_count=3000)
        quotes = [
            IndexQuoteResponse(
                code="sh000001",
                name="上证指数",
                price=3000.0,
                change=10.0,
                change_pct=0.33,
                trend=[1.0, 2.0, 3.0],
            )
        ]
        with (
            patch.object(
                at.market_stats_svc,
                "get_market_stats",
                AsyncMock(return_value=stats),
            ),
            patch.object(
                at.index_quotation_service,
                "get_index_quotes",
                AsyncMock(return_value=quotes),
            ),
        ):
            result = await at.get_market_overview.ainvoke({})

        assert result["market_stats"]["trade_date"] == "2026-08-21"
        assert result["market_stats"]["up_count"] == 3000
        assert "trend" not in result["index_quotes"][0]
        assert result["index_quotes"][0]["name"] == "上证指数"

    @pytest.mark.asyncio
    async def test_market_overview_rejects_bad_date(self) -> None:
        result = await at.get_market_overview.ainvoke({"trade_date": "2026/08/21"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_auction_summary_latest_skips_none(self) -> None:
        response = IndexAuctionTrendResponse(
            dates=[date(2026, 8, 20), date(2026, 8, 21)],
            series=[
                IndexAuctionSeries(code="sz399001", name="深证成指", values=[1.5, None]),
                IndexAuctionSeries(code="sh000001", name="上证指数", values=[2.0, 3.0]),
            ],
        )
        with patch.object(
            at.auction_service,
            "get_index_auction_trend",
            AsyncMock(return_value=response),
        ):
            result = await at.get_auction_summary.ainvoke({"days": 2})

        assert result["dates"] == ["2026-08-20", "2026-08-21"]
        by_name = {s["name"]: s for s in result["series"]}
        assert by_name["深证成指"]["latest_yi"] == 1.5
        assert by_name["上证指数"]["latest_yi"] == 3.0
