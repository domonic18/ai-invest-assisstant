"""交易 Agent 下单出口（对话路径与批次 8 定时执行共用的唯一写入口，D18）。

链路：按 agent_key 解析专属账户 → 主数据解析柜台代码 → 风控硬校验
（risk_control，参数读 trading_agent 注册行）→ 柜台下单（order_source='agent'）
→ 轻量 upsert 本地委托行（盘中日笔数风控可数，不依赖 16:00 盘后同步）。

批次 8 定时执行传 ``context='scheduled'`` 并携带 ``plan_id``（推进计划状态机）；
对话路径 context='conversation'。工具层捕获 ``AgentAccountNotDesignatedError``
转引导文案，风控拒绝以 ``RiskRejectedError`` 透出原因列表。
"""

from typing import Any, Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.exceptions import BadRequestError
from app.models.paper_trade import PaperTradeAccount, TradingAgent
from app.services.trading import account_service
from app.services.trading.client import get_client
from app.services.trading.errors import AgentAccountNotDesignatedError
from app.services.trading.paper_trade_mappers import normalize_order_rows
from app.services.trading.paper_trade_service import resolve_counter_symbol
from app.services.trading.paper_trade_sync import _upsert_orders
from app.services.trading.risk_control import (
    SIDE_BUY,
    SIDE_SELL,
    check_order_risk,
    risk_config_from_row,
)

logger = structlog.get_logger(__name__)

AgentOrderContext = Literal["conversation", "scheduled"]


class RiskRejectedError(BadRequestError):
    """风控硬校验未通过（reasons 供 LLM 转述或计划状态机记录）。"""

    default_message = "委托未通过风控校验"


async def execute_agent_order(
    session: AsyncSession,
    agent: TradingAgent,
    *,
    symbol: str,
    side: str,
    volume: int,
    price: float = 0.0,
    order_type: str = "limit",
    context: AgentOrderContext = "conversation",
    plan_id: int | None = None,
    account: PaperTradeAccount | None = None,
) -> dict[str, Any]:
    """Agent 下单唯一出口：风控硬校验 → 柜台下单 → 本地委托行即时 upsert。

    Args:
        agent: 归属 Agent 注册行（解析专属账户，风控阈值读其 risk_max_*）。
        symbol: 平台 6 位代码（或带柜台前缀完整代码，服务层按主数据解析）。
        side: ``buy`` / ``sell``（sidecar 契约，人工路径同源）。
        context: 调用来源（对话 / 定时执行），仅入日志与事件标记。
        plan_id: 批次 8 计划行 id（对话路径为 None）。
        account: 已解析的 agent 账户（批次 8 已持有时免二次查询）。

    Returns:
        ``{"cl_ord_id", "status", "risk": RiskCheckResult, "raw": 柜台响应}``。

    Raises:
        AgentAccountNotDesignatedError: 该 Agent 未绑定专属账户（工具层转引导文案）。
        BadRequestError: 代码无法识别、主数据无此代码或账户已停用。
        RiskRejectedError: 风控硬校验未通过（reasons 附于 detail）。
        PaperTradeNotConfiguredError / PaperTradeGatewayError: sidecar/柜台异常。
    """
    agent_key = agent.agent_key
    if side not in ("buy", "sell"):
        raise BadRequestError(f"side 必须为 buy/sell（当前 {side}）")
    if volume <= 0:
        raise BadRequestError(f"下单数量必须为正数（当前 {volume}）")

    if account is None:
        account = await account_service.resolve_agent_account(session, agent_key)
    if account.agent_key != agent_key:
        raise BadRequestError("目标账户不是该 Agent 的专属账户")
    if not account.is_enabled:
        raise BadRequestError("agent 专属账户已停用，禁止交易")

    risk_config = risk_config_from_row(
        max_position_pct=agent.risk_max_position_pct,
        max_total_pct=agent.risk_max_total_pct,
        max_daily_orders=agent.risk_max_daily_orders,
    )

    counter_symbol = await resolve_counter_symbol(session, symbol)
    stock_code = counter_symbol.split(".", 1)[1]
    risk_result = await check_order_risk(
        session,
        account,
        risk_config,
        stock_code=stock_code,
        side=SIDE_BUY if side == "buy" else SIDE_SELL,
        volume=volume,
        price=price,
        order_type=order_type,
    )
    if not risk_result.passed:
        raise RiskRejectedError("；".join(risk_result.reasons))

    client = get_client()
    raw = await client.place_order(
        account_service.credentials_for(account),
        counter_symbol,
        side,
        volume,
        price=price,
        order_type=order_type,
    )

    # 轻量落库：仅本笔委托 upsert（盘中日笔数风控可数；成交回报仍走 16:00 sync）
    today_rows = normalize_order_rows(
        raw,
        today_cn(),
        account_id=account.id,
        order_source=account_service.ORDER_SOURCE_AGENT,
    )
    if today_rows:
        await _upsert_orders(session, rows=today_rows)
        await session.commit()

    first = today_rows[0] if today_rows else {}
    logger.info(
        "trading_agent_order_placed",
        agent_key=agent_key,
        account_id=account.id,
        cl_ord_id=first.get("cl_ord_id"),
        symbol=counter_symbol,
        side=side,
        volume=volume,
        price=price,
        order_type=order_type,
        context=context,
        plan_id=plan_id,
        status=first.get("status"),
    )
    return {
        "cl_ord_id": str(first.get("cl_ord_id") or ""),
        "status": first.get("status"),
        "ord_rej_reason_detail": first.get("ord_rej_reason_detail"),
        "risk": risk_result,
        "raw": raw,
    }


async def cancel_agent_order(account: PaperTradeAccount, cl_ord_id: str) -> Any:
    """Agent 撤单（柜台按 accountId+clOrdId 校验归属）；撤单不占日笔数。"""
    client = get_client()
    return await client.cancel_order(account_service.credentials_for(account), cl_ord_id)


async def ensure_agent_account(
    session: AsyncSession, agent_key: str
) -> PaperTradeAccount:
    """工具层入口：按 agent_key 解析专属账户并校验启用态（未绑定转引导文案由调用方捕获）。"""
    account = await account_service.resolve_agent_account(session, agent_key)
    if not account.is_enabled:
        raise BadRequestError("agent 专属账户已停用，请联系管理员在后台启用")
    return account


__all__ = [
    "AgentAccountNotDesignatedError",
    "AgentOrderContext",
    "RiskRejectedError",
    "cancel_agent_order",
    "ensure_agent_account",
    "execute_agent_order",
]
