"""交易 Agent 账户总览工具（固定 agent 专属账户，与人工账户隔离）。

工具经 ``make_*`` 工厂按 agent_key 闭包绑定（多 Agent 基座 D24），
工具清单见 ``build_trading_tools``。
"""

from typing import Any

from langchain_core.tools import BaseTool, tool

from app.core.database import AsyncSessionLocal


def make_get_account_tool(agent_key: str) -> BaseTool:
    """构建账户总览工具（闭包绑定 agent_key）。"""

    @tool
    async def get_paper_trade_account() -> dict[str, Any]:
        """查询交易 Agent 专属模拟盘账户的实时状态：资金概况、当前持仓、未结委托。

        下单前必须先调用本工具确认可用资金与持仓（现价另用行情工具获取）。
        返回 cash（nav=总资产/available=可用资金）、positions（含市值与成本）、
        unfinished_orders（未结委托，可用 cl_ord_id 撤单）。
        """
        from app.services.trading.account_service import resolve_agent_account
        from app.services.trading.errors import (
            AgentAccountNotDesignatedError,
            PaperTradeGatewayError,
            PaperTradeNotConfiguredError,
        )
        from app.services.trading.paper_trade_service import get_overview

        async with AsyncSessionLocal() as session:
            try:
                account = await resolve_agent_account(session, agent_key)
                overview = await get_overview(session, account)
            except AgentAccountNotDesignatedError as exc:
                return {"error": str(exc), "needs_account": True}
            except PaperTradeNotConfiguredError as exc:
                return {"error": str(exc)}
            except PaperTradeGatewayError as exc:
                return {"error": f"柜台暂时不可用：{exc}"}

        cash = overview.get("cash") or {}
        return {
            **overview,
            "note": (
                "以上为掘金仿真柜台实时数据。nav 为账户总资产，available 为可用资金；"
                "T+1 限制下当日买入的股票不可当日卖出（available_volume 已修正）。"
            ),
            "cash_note": f"总资产 {cash.get('nav')}，可用资金 {cash.get('available')}",
        }

    return get_paper_trade_account
