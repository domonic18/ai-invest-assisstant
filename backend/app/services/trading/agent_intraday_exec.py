"""盘中执行链执行侧（broker 触达）：量数计算、下单推进、未结对账。

下单/撤单一律经 ``execute_agent_order``（风控硬校验与 run 留痕在彼处）；
``_execute_candidate``/``execute_tail_stop`` 把异常路径收敛为
(action, suppression_reason, extra) 返回，绝不中断 tick 主链路；
``_reconcile_pending_orders`` 尽力回填未结委托（失败下一拍重试）。
"""

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn, utc_now
from app.models.agent_trading import AgentTradePlan
from app.models.paper_trade import PaperTradeAccount, PaperTradeOrder, TradingAgent
from app.services.trading import account_service
from app.services.trading.agent_intraday_decision import (
    ACTION_EXECUTE,
    ACTION_SUPPRESS,
    SUPPRESS_ORDER_ERROR,
    SUPPRESS_POSITION_UNAVAILABLE,
    SUPPRESS_RISK_REJECTED,
    SUPPRESS_SHADOW,
)
from app.services.trading.agent_trade_service import (
    RiskRejectedError,
    execute_agent_order,
)
from app.services.trading.errors import (
    AgentAccountNotDesignatedError,
    PaperTradeGatewayError,
    PaperTradeNotConfiguredError,
)

logger = structlog.get_logger(__name__)


async def _buy_volume(account: PaperTradeAccount, plan: AgentTradePlan, *, price: float) -> int:
    """按 position_pct 目标市值折算整手买入量（科创板最低 200 股）。"""
    from app.services.trading.client import get_client
    from app.services.trading.paper_trade_mappers import normalize_cash_row

    cash = normalize_cash_row(
        await get_client().get_cash(account_service.credentials_for(account)), today_cn()
    )
    nav = float(cash["nav"]) if cash.get("nav") is not None else 0.0
    target_value = nav * float(plan.position_pct) / 100
    if target_value <= 0:
        return 0
    volume = int(target_value / price // 100) * 100
    if plan.stock_code.startswith("68") and 0 < volume < 200:
        volume = 200 if target_value >= 200 * price else 0
    return volume


async def _held_volume(account: PaperTradeAccount, stock_code: str) -> int:
    """当前持仓股数（卖出计划 / 尾盘强检卖出量）。"""
    from app.services.trading.client import get_client
    from app.services.trading.paper_trade_converters import row_stock_code, unwrap_rows

    for row in unwrap_rows(
        await get_client().get_positions(account_service.credentials_for(account))
    ):
        if row_stock_code(row) == stock_code:
            return int(row.get("volume") or 0)
    return 0


async def _execute_candidate(
    session: AsyncSession,
    agent: TradingAgent,
    account: PaperTradeAccount,
    plan: AgentTradePlan,
    *,
    price: float,
    now: datetime,
) -> tuple[str, str | None, dict[str, Any]]:
    """执行单个触发计划：shadow 只回观测语义；active 真实下单并推进状态机。

    Returns:
        (action, suppression_reason, extra_snapshot)；异常路径收敛为
        suppress + 原因，不中断本 tick 其他计划。

    Raises:
        AgentAccountNotDesignatedError: 由调用方先行解析账户避免。
    """
    if agent.intraday_exec_mode != "active":
        return ACTION_EXECUTE, SUPPRESS_SHADOW, {}
    side = "buy" if plan.plan_type == "buy" else "sell"
    volume = (
        await _buy_volume(account, plan, price=price)
        if side == "buy"
        else await _held_volume(account, plan.stock_code)
    )
    if volume <= 0:
        return ACTION_SUPPRESS, SUPPRESS_POSITION_UNAVAILABLE, {}
    try:
        result = await execute_agent_order(
            session,
            agent,
            symbol=plan.stock_code,
            side=side,
            volume=volume,
            price=price,
            context="scheduled",
            plan_id=plan.id,
            account=account,
        )
    except RiskRejectedError as exc:
        return ACTION_SUPPRESS, SUPPRESS_RISK_REJECTED, {"risk_reasons": str(exc)}
    except (PaperTradeNotConfiguredError, PaperTradeGatewayError) as exc:
        return ACTION_SUPPRESS, SUPPRESS_ORDER_ERROR, {"error": str(exc)}
    await session.execute(
        update(AgentTradePlan)
        .where(AgentTradePlan.id == plan.id)
        .values(
            status="triggered",
            triggered_cl_ord_id=result["cl_ord_id"],
            triggered_at=now,
            updated_at=utc_now(),
        )
    )
    return ACTION_EXECUTE, None, {"cl_ord_id": result["cl_ord_id"], "volume": volume}


async def execute_tail_stop(
    session: AsyncSession,
    agent: TradingAgent,
    account: PaperTradeAccount,
    *,
    stock_code: str,
    price: float,
) -> tuple[str, str | None, dict[str, Any]]:
    """尾盘止损强检下单：shadow 只回影子语义；异常收敛为 order_error 抑制。

    Returns:
        (action, suppression_reason, extra_snapshot)，语义同 ``_execute_candidate``。
    """
    if agent.intraday_exec_mode != "active":
        return ACTION_EXECUTE, SUPPRESS_SHADOW, {}
    volume = await _held_volume(account, stock_code)
    if volume <= 0:
        return ACTION_SUPPRESS, SUPPRESS_POSITION_UNAVAILABLE, {}
    try:
        order = await execute_agent_order(
            session,
            agent,
            symbol=stock_code,
            side="sell",
            volume=volume,
            price=price,
            context="scheduled",
            account=account,
        )
    except (
        RiskRejectedError,
        PaperTradeNotConfiguredError,
        PaperTradeGatewayError,
    ) as exc:
        return ACTION_SUPPRESS, SUPPRESS_ORDER_ERROR, {"error": str(exc)}
    return ACTION_EXECUTE, None, {"cl_ord_id": order["cl_ord_id"], "volume": volume}


async def _account_or_none(
    session: AsyncSession, agent_key: str
) -> PaperTradeAccount | None:
    """agent 专属账户（未绑定返回 None，触发计划按 no_account 抑制）。"""
    try:
        return await account_service.resolve_agent_account(session, agent_key)
    except AgentAccountNotDesignatedError:
        return None


#: 柜台委托终态（已成/部撤/已撤/已拒，对齐 shared/constants/paperTrade.ts
#: 状态字典）；不在终态集（含未知码）即视为未结，需盘中回填
_ORDER_TERMINAL_STATUSES = (3, 4, 5, 8)


async def _has_pending_orders(session: AsyncSession, account: PaperTradeAccount) -> bool:
    """当日 agent 来源委托是否仍有未结（非终态）——盘中回填的触发条件。"""
    pending = await session.scalar(
        select(func.count())
        .select_from(PaperTradeOrder)
        .where(
            PaperTradeOrder.paper_trade_account_id == account.id,
            PaperTradeOrder.trade_date == today_cn(),
            PaperTradeOrder.order_source == account_service.ORDER_SOURCE_AGENT,
            PaperTradeOrder.status.not_in(_ORDER_TERMINAL_STATUSES),
        )
    )
    return bool(pending)


async def _reconcile_pending_orders(session: AsyncSession, agent: TradingAgent) -> None:
    """未结委托盘中回填：触发既有单账户即时同步，成交终态 ≤ 一拍 tick。

    下单走轻量落库（只写已报），成交终态原依赖 16:00 盘后全量同步——
    盘中用户最长 2 小时看到「已报」未成交。当日仍有未结的 agent 委托时
    调 ``sync_account_now`` 回填委托/成交/资金；16:00 全量 sync 仍是
    权威对账。同步异常（含 16:00 批量同步并发锁冲突）吞掉记日志，
    下一拍重试，绝不影响 tick 主链路。
    """
    try:
        account = await _account_or_none(session, agent.agent_key)
        if account is None or not await _has_pending_orders(session, account):
            return
        from app.services.trading.paper_trade_sync import sync_account_now

        await sync_account_now(session, account)
    except Exception as exc:  # noqa: BLE001 —— 尽力而为，失败下一拍重试
        logger.warning(
            "agent_order_backfill_failed", agent_key=agent.agent_key, error=str(exc)
        )
