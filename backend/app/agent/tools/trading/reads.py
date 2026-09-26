"""交易 Agent 只读工具（批次 7）：分层复盘与当日选股清单。"""

from typing import Any, Literal

from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal


@tool
async def get_daily_review(period: Literal["day", "week", "month"] = "day") -> dict[str, Any]:
    """查询交易 Agent 模拟盘的 AI 分层复盘（只读，不触发生成）。

    Args:
        period: "day" 当日复盘 / "week" 本周复盘 / "month" 本月复盘。

    Returns:
        overall 整体评价、trades 逐笔三层判定（选股/计划/执行）、bias 倾向、
        suggestion 建议、experiences 已沉淀经验。尚未生成时返回 not_ready。
    """
    from app.services.trading import agent_review_service

    async with AsyncSessionLocal() as session:
        content = await agent_review_service.get_review(session, period=period)

    if content is None:
        return {
            "not_ready": True,
            "note": f"{period} 复盘尚未生成（日度约 16:10 生成，周五/月末自动加发周/月复盘）。",
        }
    return content.model_dump()


@tool
async def get_stock_selections() -> dict[str, Any]:
    """查询交易 Agent 当前选股清单（自选页 agent 分组同源，含选入依据与置信度）。

    Returns:
        items 为 active 选股列表（stock_code / reason / confidence / trade_date）；
        已被人工移出的标的不在列（移出全局生效，次日也不会重复选入）。
    """
    from app.services.trading import agent_plan_ops

    async with AsyncSessionLocal() as session:
        rows = await agent_plan_ops.list_active_selections(session)

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
        "note": "人工移出（removed_reason=manual）的标的全局生效，禁止再次选入。",
    }
