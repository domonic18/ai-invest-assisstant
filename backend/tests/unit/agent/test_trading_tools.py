"""交易 Agent 工具装配守卫单测（工具清单钉死 + 补采派发/画线渲染参数断言，mock 不触网）。"""

import json
from contextlib import ExitStack
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools.trading import TOOLS_VERSION, build_trading_tools
from app.agent.tools.trading.backfill import FINANCIAL_MAX_CODES, collect_financial_data
from app.schemas.drawing import (
    AiKlineDrawingGroupResponse,
    AiKlineDrawingItemSchema,
    KlineDrawingAnchorSchema,
    KlineDrawingsResponse,
    KlineDrawingStyleSchema,
    UserKlineDrawingResponse,
)


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
            # 画线与视觉自检
            "get_kline_drawings",
            "persist_ai_kline_drawings",
            "render_kline_drawings",
        ]

    def test_tools_version_tracks_list_change(self) -> None:
        """钉死当前版本：清单再变更时须与 test_tool_list_pinned 同一提交 bump。"""
        assert TOOLS_VERSION == 6


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
            "collector.runtime.dispatcher.dispatch_collector_task",
            AsyncMock(),
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


def _kline_bars(n: int = 10) -> list[dict]:
    """升序日K构造数据（日期连续仅作锚点对齐用，非真实交易日历）。"""
    return [
        {
            "date": f"2026-09-{i + 1:02d}",
            "open": 10.0 + i * 0.1,
            "high": 10.5 + i * 0.1,
            "low": 9.8 + i * 0.1,
            "close": 10.2 + i * 0.1,
            "volume": 1000 + i,
        }
        for i in range(n)
    ]


def _drawings_response() -> KlineDrawingsResponse:
    anchor = KlineDrawingAnchorSchema
    return KlineDrawingsResponse(
        user=[
            UserKlineDrawingResponse(
                id="u1",
                target_type="stock",
                target_code="600519",
                period="daily",
                drawing_type="trendline",
                anchors=[anchor(date="2026-09-02", price=10.0), anchor(date="2026-09-08", price=10.8)],
                style=KlineDrawingStyleSchema(color="#f59e0b", line_style="dashed", width=2),
            ),
            UserKlineDrawingResponse(
                id="u2",
                target_type="stock",
                target_code="600519",
                period="weekly",
                drawing_type="hline",
                anchors=[anchor(date="", price=11.0)],
                style=KlineDrawingStyleSchema(color="#22d3ee", line_style="solid", width=1),
            ),
        ],
        ai=[
            AiKlineDrawingGroupResponse(
                target_type="stock",
                target_code="600519",
                period="daily",
                skill_id="kline-smart-drawing",
                trade_date=date(2026, 9, 10),
                drawings=[
                    AiKlineDrawingItemSchema(
                        drawing_type="hline",
                        anchors=[anchor(date="", price=10.5)],
                        label="压力位",
                        reason="两测回落",
                    )
                ],
            )
        ],
    )


def _render_patches(vision: bool):
    """渲染工具全链路 mock（K线取数/画线清单/MinIO/视觉能力判定），apply() 逐项 patch。"""
    from app.agent.tools.trading.drawings import KlineDrawingVisualCheck

    minio = AsyncMock()
    minio.upload_file.return_value = "kline-drawings/u1/600519-daily-0.png"
    minio.get_presigned_url.return_value = "https://minio.local/signed"
    structured = AsyncMock(
        return_value=KlineDrawingVisualCheck(
            summary="两条线均落在K线实体上",
            readings=[{"label": "压力位", "kind": "hline", "reading": "压在 10.5 密集区"}],
            anomalies=[],
        )
    )
    patches = {
        "app.agent.tools.trading.drawings.get_stock_kline": AsyncMock(
            return_value={"name": "贵州茅台", "bars": _kline_bars()}
        ),
        "app.agent.tools.trading.drawings.KlineDrawingService": lambda session: AsyncMock(
            list_drawings=AsyncMock(return_value=_drawings_response())
        ),
        "app.agent.tools.trading.drawings.get_minio_service": lambda: minio,
        "app.agent.tools.trading.drawings._bound_model_supports_vision": AsyncMock(return_value=vision),
        "app.agent.runtime.structured.run_structured": structured,
    }

    def apply():
        stack = ExitStack()
        for target, mock in patches.items():
            stack.enter_context(patch(target, mock))
        return stack

    return {"minio": minio, "structured": structured, "apply": apply}


def _invoke_render(**overrides):
    """裸 ainvoke 无 tool_call_id 时 langchain 直接返回 content（不包 ToolMessage）。"""
    from app.agent.tools.trading.drawings import make_render_kline_drawings_tool

    tool = make_render_kline_drawings_tool("short-line")
    args = {"target_type": "stock", "target_code": "600519", "period": "daily", "limit": 50} | overrides
    return tool.ainvoke(args, config={"configurable": {"user_id": 1}})


@pytest.mark.unit
class TestRenderKlineDrawings:
    @pytest.mark.asyncio
    async def test_direct_vision_path_returns_image_block(self) -> None:
        """绑定模型支持视觉：content blocks 直带图像，不落 run_structured。"""
        ctx = _render_patches(vision=True)
        with ctx["apply"]():
            content = await _invoke_render()

        assert content[0]["type"] == "text"
        meta = json.loads(content[0]["text"])
        assert meta["image_url"] == "https://minio.local/signed"
        assert meta["drawing_count"] == 2  # 仅 daily 周期：user trendline + ai hline
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        ctx["structured"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_vision_slot_fallback_returns_structured_check(self) -> None:
        """绑定模型无视觉能力：降级 run_structured(vision=True)，返回文本结论。"""
        ctx = _render_patches(vision=False)
        with ctx["apply"]():
            content = await _invoke_render()

        meta = json.loads(content[0]["text"])
        assert meta["consumption"] == "vision_slot"
        assert meta["visual_check"]["summary"].startswith("两条线")
        assert all(block["type"] == "text" for block in content)

    @pytest.mark.asyncio
    async def test_vision_not_configured_returns_url_only(self) -> None:
        from app.services.admin.llm_config_service import LLMConfigNotConfiguredError

        ctx = _render_patches(vision=False)
        ctx["structured"].side_effect = LLMConfigNotConfiguredError("no vision model")
        with ctx["apply"]():
            content = await _invoke_render()

        meta = json.loads(content[0]["text"])
        assert meta["consumption"] == "none"
        assert meta["visual_check"] is None
        assert "视觉模型" in meta["note"]

    @pytest.mark.asyncio
    async def test_rejects_non_stock_target(self) -> None:
        ctx = _render_patches(vision=True)
        with ctx["apply"]():
            content = await _invoke_render(target_type="sector")

        meta = json.loads(content[0]["text"])
        assert "仅支持个股" in meta["error"]
        ctx["minio"].upload_file.assert_not_awaited()
