"""交易 Agent 交易计划工具（批次 7）：对话内制定 / 查询 / 取消当日计划。

计划行与 19:00 定时生成同表同状态机（active → triggered → executed /
expired / cancelled）；对话制定的计划同样受批次 8 盘中执行器消费。
工具经 ``make_*`` 工厂按 agent_key 闭包绑定（多 Agent 基座 D24）。
"""

from typing import Any

from langchain_core.tools import BaseTool, tool

from app.agent.tools.page_event import page_event
from app.core.database import AsyncSessionLocal


def make_make_plan_tool(agent_key: str) -> BaseTool:
    """构建制定计划工具（闭包绑定 agent_key）。"""

    @tool
    async def make_trade_plan(
        stock_code: str,
        plan_type: str,
        strategy: str,
        stop_loss: float,
        position_pct: float,
        basis: str,
        buy_zone_low: float | None = None,
        buy_zone_high: float | None = None,
        target_price: float | None = None,
    ) -> dict[str, Any]:
        """为交易 Agent 制定一条交易计划（写入当日计划表，供盘中条件触发执行）。

        Args:
            stock_code: 6 位股票代码，如 "600000"。
            plan_type: "buy" 或 "sell"。buy 必须提供 buy_zone_low/high；
                sell 必须提供 target_price。
            strategy: 一句话策略描述（如「回踩 5 日线买入」）。
            stop_loss: 止损价（两类计划均必填）。
            position_pct: 建议仓位占比（0-100）。
            basis: 计划依据（引用复盘/数据，供事后归因）。
            buy_zone_low: 买点区间下沿（buy 必填）。
            buy_zone_high: 买点区间上沿（buy 必填）。
            target_price: 止盈价（sell 必填）。

        Returns:
            计划 id 与状态。用户未确认前不要调用本工具（auto_exec_enabled
            开启时计划会被盘中自动执行）。
        """
        from app.core.exceptions import AppError
        from app.services.market import trade_calendar_service
        from app.services.trading import agent_plan_ops

        if plan_type not in ("buy", "sell"):
            return {"error": f"plan_type 必须为 buy 或 sell（当前 {plan_type}）"}
        if not 0 < position_pct <= 100:
            return {"error": f"position_pct 须在 (0, 100] 内（当前 {position_pct}）"}

        async with AsyncSessionLocal() as session:
            plan_date = await trade_calendar_service.resolve_latest_trade_date(session)
            try:
                plan = await agent_plan_ops.create_plan(
                    session,
                    agent_key,
                    plan_date=plan_date,
                    stock_code=stock_code.strip(),
                    plan_type=plan_type,
                    strategy=strategy,
                    stop_loss=stop_loss,
                    position_pct=position_pct,
                    basis=basis,
                    buy_zone_low=buy_zone_low,
                    buy_zone_high=buy_zone_high,
                    target_price=target_price,
                )
            except AppError as exc:
                return {"error": str(exc)}

        return {
            "success": True,
            "plan_id": plan.id,
            "plan_date": plan.plan_date.isoformat(),
            "stock_code": plan.stock_code,
            "plan_type": plan.plan_type,
            "status": plan.status,
            "__event__": page_event(
                "paper_trading.complete",
                action="plan",
                agent_key=agent_key,
                plan_id=plan.id,
                stock_code=plan.stock_code,
                plan_type=plan.plan_type,
            ),
            "note": (
                "计划已写入当日交易计划。auto_exec_enabled 开启时，盘中触达"
                "买点区间/止盈/止损价会自动下单；关闭时仅作对话参考。"
            ),
        }

    return make_trade_plan


def make_list_plans_tool(agent_key: str) -> BaseTool:
    """构建计划查询工具（闭包绑定 agent_key）。"""

    @tool
    async def list_trade_plans() -> dict[str, Any]:
        """查询交易 Agent 当日（最近交易日）的全部交易计划及状态。

        Returns:
            items 为计划列表（plan_type / strategy / 买卖点 / 止损 / 仓位 /
            status）。status：active 待触发、triggered 已触发下单、executed 已
            成交、expired 当日未触发失效、cancelled 已取消。
        """
        from app.services.market import trade_calendar_service
        from app.services.trading import agent_plan_ops

        async with AsyncSessionLocal() as session:
            plan_date = await trade_calendar_service.resolve_latest_trade_date(session)
            rows = await agent_plan_ops.list_plans(session, agent_key, plan_date=plan_date)

        return {
            "trade_date": plan_date.isoformat(),
            "items": [
                {
                    "id": r.id,
                    "stock_code": r.stock_code,
                    "plan_type": r.plan_type,
                    "strategy": r.strategy,
                    "buy_zone_low": float(r.buy_zone_low) if r.buy_zone_low is not None else None,
                    "buy_zone_high": float(r.buy_zone_high) if r.buy_zone_high is not None else None,
                    "target_price": float(r.target_price) if r.target_price is not None else None,
                    "stop_loss": float(r.stop_loss),
                    "position_pct": float(r.position_pct),
                    "status": r.status,
                    "triggered_cl_ord_id": r.triggered_cl_ord_id,
                }
                for r in rows
            ],
        }

    return list_trade_plans


def make_cancel_plan_tool(agent_key: str) -> BaseTool:
    """构建计划取消工具（闭包绑定 agent_key）。"""

    @tool
    async def cancel_trade_plan(plan_id: int) -> dict[str, Any]:
        """取消交易 Agent 的一条当日 active 计划（已触发 triggered 的不可取消）。

        Args:
            plan_id: 计划 id（list_trade_plans 返回的 id）。
        """
        from app.core.exceptions import AppError
        from app.services.trading import agent_plan_ops

        async with AsyncSessionLocal() as session:
            try:
                plan = await agent_plan_ops.cancel_plan(session, agent_key, plan_id=plan_id)
            except AppError as exc:
                return {"error": str(exc)}

        return {
            "success": True,
            "plan_id": plan.id,
            "status": plan.status,
            "__event__": page_event(
                "paper_trading.complete",
                action="plan_cancel",
                agent_key=agent_key,
                plan_id=plan.id,
            ),
            "note": "计划已取消，盘中执行器不再消费该计划。",
        }

    return cancel_trade_plan
