"""交易 Agent 下单/撤单工具（唯一出口走服务层，风控硬校验内聚）。

拒单三类转述：风控拦截（RiskRejectedError.reasons）、柜台受理后拒绝
（status=8 + ord_rej_reason_detail）、柜台/网络错误（GatewayError 原文）。
成功下单嵌 ``paper_trading.complete`` 页面事件驱动交易 Agent 页刷新。
"""

from typing import Any

from langchain_core.tools import tool

from app.agent.tools.page_event import page_event
from app.core.database import AsyncSessionLocal
from app.services.trading.errors import (
    AgentAccountNotDesignatedError,
    PaperTradeGatewayError,
    PaperTradeNotConfiguredError,
)

# 掘金柜台 OrderStatus：8 = 已拒（受理后资金/持仓/参数校验不过）
_COUNTER_STATUS_REJECTED = 8


@tool
async def place_paper_trade_order(
    symbol: str,
    side: str,
    volume: int,
    price: float = 0.0,
    order_type: str = "limit",
) -> dict[str, Any]:
    """以交易 Agent 专属账户提交模拟盘委托（下单前必须已获用户确认）。

    Args:
        symbol: 6 位股票代码，如 "600000"（也接受 SHSE.600000 完整形式）。
        side: "buy" 或 "sell"。
        volume: 委托数量（股）。主板 100 股整数倍；科创板最低 200 股。
        price: 委托价格。限价单必填（建议现价 ±3% 内，明显偏离会被质疑）；
            市价单传 0。
        order_type: "limit"（默认）或 "market"。

    Returns:
        成功返回 cl_ord_id 与状态；被风控拦截时 reasons 为具体原因
        （如实转述给用户，不要重试同参数下单）。
    """
    from app.services.trading.agent_trade_service import RiskRejectedError, execute_agent_order

    if side not in ("buy", "sell"):
        return {"error": f"side 必须为 buy 或 sell（当前 {side}）"}

    async with AsyncSessionLocal() as session:
        try:
            result = await execute_agent_order(
                session,
                symbol=symbol,
                side=side,
                volume=volume,
                price=price,
                order_type=order_type,
                context="conversation",
            )
        except AgentAccountNotDesignatedError as exc:
            return {"error": str(exc), "needs_account": True}
        except RiskRejectedError as exc:
            return {
                "success": False,
                "rejected": True,
                "error": str(exc),
                "note": "委托被风控规则拦截，请向用户如实转述原因；调整数量或标的后才能再次提交。",
            }
        except PaperTradeNotConfiguredError as exc:
            return {"error": str(exc)}
        except PaperTradeGatewayError as exc:
            return {"error": f"柜台返回错误：{exc}"}

    cl_ord_id = result.get("cl_ord_id") or ""
    if result.get("status") == _COUNTER_STATUS_REJECTED:
        return {
            "success": False,
            "rejected": True,
            "cl_ord_id": cl_ord_id,
            "reason": result.get("ord_rej_reason_detail") or "柜台拒绝（原因未返回）",
            "note": "柜台已拒绝该委托，请向用户转述原因。",
        }

    return {
        "success": True,
        "cl_ord_id": cl_ord_id,
        "status": result.get("status"),
        "symbol": symbol,
        "side": side,
        "volume": volume,
        "price": price,
        "__event__": page_event(
            "paper_trading.complete",
            action="order",
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side,
            volume=volume,
        ),
        "note": (
            "委托已报送柜台。成交确认以柜台回报为准（执行动态已刷新）；"
            "如需取消未成交委托，用 cl_ord_id 调撤单工具。"
        ),
    }


@tool
async def cancel_paper_trade_order(cl_ord_id: str) -> dict[str, Any]:
    """撤销交易 Agent 专属账户的一笔未成交委托。

    Args:
        cl_ord_id: 下单工具返回的委托号（也可从未结委托查询中获得）。
    """
    from app.core.exceptions import AppError
    from app.services.trading.agent_trade_service import cancel_agent_order, ensure_agent_account

    if not cl_ord_id.strip():
        return {"error": "cl_ord_id 不能为空"}

    async with AsyncSessionLocal() as session:
        try:
            account = await ensure_agent_account(session)
            await cancel_agent_order(account, cl_ord_id.strip())
        except AgentAccountNotDesignatedError as exc:
            return {"error": str(exc), "needs_account": True}
        except PaperTradeGatewayError as exc:
            return {"error": f"柜台返回错误：{exc}"}
        except PaperTradeNotConfiguredError as exc:
            return {"error": str(exc)}
        except AppError as exc:
            return {"error": str(exc)}

    return {
        "success": True,
        "cl_ord_id": cl_ord_id,
        "__event__": page_event(
            "paper_trading.complete",
            action="cancel",
            cl_ord_id=cl_ord_id,
        ),
        "note": "撤单请求已报送柜台，撤销结果以柜台回报为准。",
    }
