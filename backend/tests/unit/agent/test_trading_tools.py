"""交易 Agent 工具装配守卫单测（工具清单钉死 + 补采派发参数断言，mock 不触网）。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools.trading import TOOLS_VERSION, build_trading_tools
from app.agent.tools.trading.backfill import FINANCIAL_MAX_CODES, collect_financial_data


@pytest.mark.unit
class TestBuildTradingTools:
    def test_tool_list_pinned(self) -> None:
        """增删工具必须显式更新本断言并同步 bump TOOLS_VERSION（缓存指纹失效）。"""
        tools = build_trading_tools("short-line")
        assert [t.name for t in tools] == [
            "get_paper_trade_account",
            # 行情查询
            "get_stock_quote",
            "get_stock_kline",
            "get_stock_technical",
            "get_stock_emotion_context",
            "get_stock_fund_flow",
            "get_trade_calendar",
            "ask_user",
            # 模拟盘写路径（agent_key 闭包绑定，名称不受 agent_key 影响）
            "place_paper_trade_order",
            "cancel_paper_trade_order",
            "get_daily_review",
            "get_stock_selections",
            "make_trade_plan",
            "list_trade_plans",
            "cancel_trade_plan",
            # 财务查询与数据自愈
            "query_financial_data",
            "download_financial_reports",
            "query_financial_reports",
            "summarize_financial_report",
            "collect_market_data",
            "collect_financial_data",
        ]

    def test_tools_version_tracks_list_change(self) -> None:
        """钉死当前版本：清单再变更时须与 test_tool_list_pinned 同一提交 bump。"""
        assert TOOLS_VERSION == 5


@pytest.mark.unit
class TestCollectFinancialData:
    @pytest.mark.asyncio
    async def test_dispatches_deduped_symbols(self) -> None:
        with patch(
            "collector.runtime.dispatcher.dispatch_collector_task", AsyncMock()
        ) as mock_dispatch:
            result = await collect_financial_data.ainvoke(
                {"stock_codes": ["000001", "600519", "000001"]}
            )

        assert result["symbols"] == ["000001", "600519"]
        assert mock_dispatch.await_args.args[1] == "financial-statement"
        assert mock_dispatch.await_args.args[2] == {"symbols": ["000001", "600519"]}
        assert "验证" in result["note"]

    @pytest.mark.asyncio
    async def test_rejects_invalid_codes(self) -> None:
        result = await collect_financial_data.ainvoke({"stock_codes": ["1", "abc"]})
        assert "error" in result
        assert "非法代码" in result["error"]

    @pytest.mark.asyncio
    async def test_rejects_empty_after_validation(self) -> None:
        result = await collect_financial_data.ainvoke({"stock_codes": []})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_clamps_to_max_codes_with_note(self) -> None:
        codes = [f"{i:06d}" for i in range(FINANCIAL_MAX_CODES + 5)]
        with patch(
            "collector.runtime.dispatcher.dispatch_collector_task", AsyncMock()
        ):
            result = await collect_financial_data.ainvoke({"stock_codes": codes})

        assert len(result["symbols"]) == FINANCIAL_MAX_CODES
        assert "补齐" in result["note"]

    @pytest.mark.asyncio
    async def test_dispatch_failure_returns_safe_error(self) -> None:
        with patch(
            "collector.runtime.dispatcher.dispatch_collector_task",
            AsyncMock(side_effect=RuntimeError("connection refused secret-dsn")),
        ):
            result = await collect_financial_data.ainvoke({"stock_codes": ["000001"]})

        assert result == {"error": "财务报表补采任务派发失败，请稍后重试或检查采集服务状态"}
        assert "secret-dsn" not in str(result)
