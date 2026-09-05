"""assistant_tools 工具层单测（mock service，不触网不连库）。"""

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.runtime import assistant_tools as at
from app.agent.tools import market_tools as mt
from app.schemas.capital_fund_flow_sector import (
    SectorFlowSeries,
    SectorFlowTrendResponse,
)
from app.schemas.chain import ChainAnalyzeResponse
from app.schemas.market import (
    CollectTaskResult,
    IndexQuoteResponse,
    MarketStatsResponse,
)
from app.schemas.stock import (
    IndexAuctionSeries,
    IndexAuctionTrendResponse,
)


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


@pytest.fixture(autouse=True)
def no_db(monkeypatch):
    monkeypatch.setattr(at, "AsyncSessionLocal", lambda: _fake_session())


@pytest.mark.unit
class TestBuildAssistantTools:
    def test_returns_twenty_tools(self) -> None:
        tools = at.build_assistant_tools()
        names = [t.name for t in tools]
        assert names == [
            "get_stock_quote",
            "get_stock_kline",
            "query_financial_data",
            "search_news",
            "search_vector_kb",
            "get_sector_fund_flow",
            "get_sector_overview",
            "get_market_overview",
            "get_limit_up_ladder",
            "get_index_technical",
            "get_auction_summary",
            "get_trade_calendar",
            "query_industry_companies",
            "persist_chain_analysis",
            "persist_stock_daily_analysis",
            "persist_market_review",
            "collect_market_data",
            "query_financial_reports",
            "download_financial_reports",
            "summarize_financial_report",
        ]


@pytest.mark.unit
class TestTradeCalendarTool:
    @pytest.mark.asyncio
    async def test_returns_now_today_and_trading_days(self) -> None:
        with (
            patch("app.agent.tools.market_tools.now_cn") as mock_now,
            patch.object(
                at.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 4)),
            ),
            patch.object(
                at.trade_calendar_service,
                "is_trading_day",
                AsyncMock(return_value=False),
            ),
        ):
            result = await at.get_trade_calendar.ainvoke({})

        assert result["today"] == mock_now.return_value.date().isoformat()
        assert result["latest_trading_day"] == "2026-09-04"
        assert result["today_is_trading_day"] is False
        assert "now" in result


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
            "app.services.chain.chain_service.persist_analysis_result",
            AsyncMock(return_value=version),
        ) as m:
            result = await at.persist_chain_analysis.ainvoke(
                {"industry": "半导体", "result": result_payload},
                {"configurable": {"user_id": 7}},
            )
        m.assert_awaited_once()
        assert m.await_args.kwargs["user_id"] == 7
        assert result["version_id"] == 123
        assert result["version_no"] == 5
        assert result["__event__"]["type"] == "industry_chain.analysis_complete"


@pytest.mark.unit
class TestStockDailyAnalysisTool:
    @pytest.mark.asyncio
    async def test_persists_sections_and_emits_event(self) -> None:
        cfg = MagicMock()
        cfg.provider = "anthropic"
        cfg.model_name = "kimi"
        analysis = MagicMock()
        analysis.stock_code = "600519"
        analysis.stock_name = "贵州茅台"
        analysis.trade_date = date(2026, 9, 4)
        analysis.sections = [MagicMock(title="操作策略")]
        sections = {
            "intraday_review": "盘面解读",
            "key_events": "关键事件",
            "strategy": "操作策略",
            "risk_lines": "风险与止损",
        }
        with (
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.stock_daily_analysis_service.persist_stock_analysis",
                AsyncMock(return_value=analysis),
            ) as persist_mock,
        ):
            result = await at.persist_stock_daily_analysis.ainvoke(
                {
                    "stock_code": "600519",
                    "trade_date": "2026-09-04",
                    "sections": sections,
                }
            )

        _, kwargs = persist_mock.await_args
        assert kwargs["trade_date"] == date(2026, 9, 4)
        assert kwargs["contents"] == sections
        assert kwargs["model"] == "anthropic/kimi"
        assert result["stock_code"] == "600519"
        assert result["stock_name"] == "贵州茅台"
        assert result["section_titles"] == ["操作策略"]
        assert result["__event__"] == {
            "type": "stock_daily_analysis.complete",
            "stock_code": "600519",
            "trade_date": "2026-09-04",
        }

    @pytest.mark.asyncio
    async def test_rejects_bad_trade_date(self) -> None:
        result = await at.persist_stock_daily_analysis.ainvoke(
            {"stock_code": "600519", "trade_date": "2026/09/04", "sections": {}}
        )
        assert "error" in result


@pytest.mark.unit
class TestFinancialReportTools:
    @pytest.mark.asyncio
    async def test_query_financial_reports(self) -> None:
        item = MagicMock()
        item.id = 7
        item.stock_code = "000001"
        item.report_type = "annual"
        item.report_date = date(2025, 12, 31)
        item.original_name = "平安银行2025年报.pdf"
        item.file_path = "financial_reports/000001_2025_annual.pdf"
        item.summary = "summary text"
        item.created_at = date(2026, 4, 1)

        mock_service = MagicMock()
        mock_service.list_reports = AsyncMock(return_value=([item], 1))
        with patch(
            "app.services.reports.financial_report_service.FinancialReportService",
            return_value=mock_service,
        ):
            result = await at.query_financial_reports.ainvoke(
                {"stock_code": "000001", "report_type": "annual"}
            )
        assert result["total"] == 1
        assert result["reports"][0]["id"] == 7
        assert result["reports"][0]["has_pdf"] is True
        assert result["reports"][0]["has_summary"] is True

    @pytest.mark.asyncio
    async def test_download_financial_reports(self) -> None:
        log = MagicMock()
        log.id = 42
        log.status = "pending"
        mock_service = MagicMock()
        mock_service.trigger_collect = AsyncMock(return_value=log)
        with patch(
            "app.services.reports.financial_report_service.FinancialReportService",
            return_value=mock_service,
        ):
            result = await at.download_financial_reports.ainvoke(
                {"stock_code": "000001", "report_types": ["annual", "q3"]}
            )
        assert result["log_id"] == 42
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_summarize_financial_report(self) -> None:
        mock_service = MagicMock()
        mock_service.summarize_report = AsyncMock(
            return_value={"summary": "营收增长 12%", "cached": False}
        )
        with patch(
            "app.services.reports.financial_report_service.FinancialReportService",
            return_value=mock_service,
        ):
            result = await at.summarize_financial_report.ainvoke({"report_id": 7})
        assert result["summary"] == "营收增长 12%"

    @pytest.mark.asyncio
    async def test_query_financial_reports_rejects_bad_date(self) -> None:
        result = await at.query_financial_reports.ainvoke(
            {"stock_code": "000001", "start_date": "2024/01/01"}
        )
        assert "error" in result


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


def _review_persist_mocks() -> tuple[MagicMock, AsyncMock]:
    cfg = MagicMock()
    cfg.provider = "anthropic"
    cfg.model_name = "kimi"
    response = SimpleNamespace(trade_date=date(2026, 9, 4), sections=[])
    return cfg, AsyncMock(return_value=response)


@pytest.mark.unit
class TestReviewLatencyAnchor:
    def setup_method(self) -> None:
        mt._review_gen_start = None

    @pytest.mark.asyncio
    async def test_latency_measured_from_first_data_tool_to_persist(self) -> None:
        cfg, persist_mock = _review_persist_mocks()
        stats = MarketStatsResponse(trade_date=date(2026, 8, 21), up_count=3000)
        fake_time = MagicMock()
        fake_time.monotonic = MagicMock(side_effect=[100.0, 165.5])
        with (
            patch.object(mt, "time", fake_time),
            patch.object(
                at.market_stats_svc,
                "get_market_stats",
                AsyncMock(return_value=stats),
            ),
            patch.object(
                at.index_quotation_service, "get_index_quotes", AsyncMock(return_value=[])
            ),
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.market_review_generator.persist_market_review_result",
                persist_mock,
            ),
        ):
            await at.get_market_overview.ainvoke({})
            result = await mt.persist_market_review.ainvoke(
                {"trade_date": "2026-09-04", "sections": {"overview": "x"}}
            )

        assert result["trade_date"] == "2026-09-04"
        assert persist_mock.await_args.kwargs["latency_ms"] == 65500

    @pytest.mark.asyncio
    async def test_persist_without_data_tool_reports_zero(self) -> None:
        cfg, persist_mock = _review_persist_mocks()
        with (
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.market_review_generator.persist_market_review_result",
                persist_mock,
            ),
        ):
            await mt.persist_market_review.ainvoke(
                {"trade_date": "2026-09-04", "sections": {"overview": "x"}}
            )

        assert persist_mock.await_args.kwargs["latency_ms"] == 0

    @pytest.mark.asyncio
    async def test_stale_anchor_reports_zero_without_fresh_data_call(self) -> None:
        mt._review_gen_start = -2000.0
        cfg, persist_mock = _review_persist_mocks()
        fake_time = MagicMock()
        fake_time.monotonic = MagicMock(side_effect=[200.0])
        with (
            patch.object(mt, "time", fake_time),
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.market_review_generator.persist_market_review_result",
                persist_mock,
            ),
        ):
            await mt.persist_market_review.ainvoke(
                {"trade_date": "2026-09-04", "sections": {"overview": "x"}}
            )

        assert persist_mock.await_args.kwargs["latency_ms"] == 0
