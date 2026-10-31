"""交易 Agent 只读工具（批次 7）：分层复盘与当日选股清单。

工具经 ``make_*`` 工厂按 agent_key 闭包绑定（多 Agent 基座 D24）。
"""

from datetime import date
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool

from app.core.database import AsyncSessionLocal


def make_get_review_tool(agent_key: str) -> BaseTool:
    """构建复盘查询工具（闭包绑定 agent_key）。"""

    @tool
    async def get_daily_review(
        period: Literal["day", "week", "month", "quarter", "half_year", "year"] | None = None,
        trade_date: str | None = None,
        scope: Literal["current", "previous"] = "current",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """查询交易 Agent 模拟盘的 AI 分层复盘（只读，不触发生成）。

        Args:
            period: "day" 日度 / "week" 周度 / "month" 月度 / "quarter" 季度 /
                "half_year" 半年度 / "year" 年度。仅给区间时可省略（按跨度映射）。
            trade_date: 基准交易日 YYYY-MM-DD，缺省取最新交易日。
            scope: "current" 本期 / "previous" 上一完整周期。
            start_date/end_date: 自定义区间 YYYY-MM-DD（须成对）。

        Returns:
            overall 整体评价、trades 逐笔三层判定（选股/计划/执行）、bias 倾向、
            suggestion 建议、experiences 已沉淀经验。尚未生成时返回 not_ready。
        """
        from app.services.trading import agent_review_service

        def _parse(raw: str | None, name: str) -> tuple[date | None, dict[str, Any] | None]:
            if not raw:
                return None, None
            try:
                return date.fromisoformat(raw), None
            except ValueError:
                return None, {"error": f"无效的 {name}：{raw}（应为 YYYY-MM-DD）"}

        parsed_date, date_error = _parse(trade_date, "trade_date")
        if date_error:
            return date_error
        parsed_start, start_error = _parse(start_date, "start_date")
        if start_error:
            return start_error
        parsed_end, end_error = _parse(end_date, "end_date")
        if end_error:
            return end_error
        if (parsed_start is None) != (parsed_end is None):
            return {"error": "自定义区间须同时提供 start_date 与 end_date"}
        resolved_period = period or (
            None if parsed_start is not None else "day"
        )

        from app.core.exceptions import AppError

        try:
            request = agent_review_service.ReviewWindowRequest.from_values(
                period=resolved_period,
                trade_date=parsed_date,
                scope=scope,
                start_date=parsed_start,
                end_date=parsed_end,
            )
            async with AsyncSessionLocal() as session:
                content = await agent_review_service.get_review(
                    session, agent_key, request
                )
        except AppError as exc:
            return {"error": str(exc)}

        if content is None:
            window_text = (
                f"{parsed_start.isoformat()} 至 {parsed_end.isoformat()}"
                if parsed_start and parsed_end
                else f"{resolved_period or '自定义区间'}"
            )
            return {
                "not_ready": True,
                "note": (
                    f"{window_text} 复盘尚未生成（日/周/月有盘后定时生成；"
                    "季/半年/年与上期/自定义区间需经页面或 "
                    "generate_trading_review 按需生成）。"
                ),
            }
        return content.model_dump()

    return get_daily_review


def make_get_selections_tool(agent_key: str) -> BaseTool:
    """构建选股查询工具（闭包绑定 agent_key）。"""

    @tool
    async def get_stock_selections() -> dict[str, Any]:
        """查询交易 Agent 当前选股清单（自选页 agent 分组同源，含选入依据与置信度）。

        Returns:
            items 为 active 选股列表（stock_code / reason / confidence / trade_date）；
            已被人工移出的标的不在列（移出按 Agent 生效，次日也不会重复选入）。
        """
        from app.services.trading import agent_plan_ops

        async with AsyncSessionLocal() as session:
            rows = await agent_plan_ops.list_active_selections(session, agent_key)

        return {
            "items": [
                {
                    "id": r.id,
                    "stock_code": r.stock_code,
                    "reason": r.reason,
                    "confidence": float(r.confidence) if r.confidence is not None else None,
                    "trade_date": r.trade_date.isoformat(),
                }
                for r in rows
            ],
            "note": "人工移出（removed_reason=manual）的标的按 Agent 生效，禁止再次选入。",
        }

    return get_stock_selections
