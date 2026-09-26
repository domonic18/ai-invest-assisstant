"""交易 Agent 计划与选股的查询/人工干预服务（批次 7，D17 干预面；多 Agent D23）。

admin 端点与对话工具共用：当日计划查询（TradingAgent 页「今日交易计划」
区块）、计划人工取消、选股查询（自选页 agent 分组合并视图）与人工移出
（removed_reason='manual'，按 Agent 生效、次日不重复选入）。
全部查询按 agent_key 维度过滤。
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.agent_trading import AgentStockSelection, AgentTradePlan
from app.models.paper_trade import PaperTradeExecution
from app.models.stock import StockBasic
from app.models.watchlist import UserWatchlistGroup
from app.schemas.paper_trade import TradingAgentPlanResponse

logger = structlog.get_logger(__name__)

AGENT_GROUP_NAME = "交易 Agent 自选"

PLAN_TYPES: tuple[str, ...] = ("buy", "sell")


@dataclass(slots=True)
class AgentGroupView:
    """自选页 agent 分组合并视图：分组行 + active 选股条目。"""

    group: UserWatchlistGroup
    selections: list[AgentStockSelection]


async def list_plans(
    session: AsyncSession, agent_key: str, *, plan_date: date
) -> list[AgentTradePlan]:
    """指定 Agent 在计划日的全部计划（前端按状态分色渲染）。"""
    rows = await session.execute(
        select(AgentTradePlan)
        .where(AgentTradePlan.agent_key == agent_key, AgentTradePlan.plan_date == plan_date)
        .order_by(AgentTradePlan.id.asc())
    )
    return list(rows.scalars().all())


async def _held_volumes(
    session: AsyncSession, agent_key: str, plan_date: date, codes: list[str]
) -> dict[str, int]:
    """截至计划日按成交聚合的持仓股数（side 加减，净持有 > 0 才计入）。

    execution.symbol 带柜台前缀（SHSE.600000），按 6 位代码后缀映射回
    stock_code；未绑定专属账户返回空映射（wire 为 None，前端显示 -）。
    """
    from app.services.trading.account_service import resolve_agent_account
    from app.services.trading.errors import AgentAccountNotDesignatedError

    try:
        account = await resolve_agent_account(session, agent_key)
    except AgentAccountNotDesignatedError:
        return {}
    wanted = set(codes)
    rows = await session.execute(
        select(
            PaperTradeExecution.symbol,
            PaperTradeExecution.side,
            func.sum(PaperTradeExecution.volume),
        )
        .where(
            PaperTradeExecution.paper_trade_account_id == account.id,
            PaperTradeExecution.trade_date <= plan_date,
        )
        .group_by(PaperTradeExecution.symbol, PaperTradeExecution.side)
    )
    agg: dict[str, int] = {}
    for symbol, side, volume in rows.all():
        code = str(symbol).split(".")[-1]
        if code not in wanted:
            continue
        delta = int(volume or 0)
        if side == 1:
            agg[code] = agg.get(code, 0) + delta
        elif side == 2:
            agg[code] = agg.get(code, 0) - delta
    return {code: volume for code, volume in agg.items() if volume > 0}


async def list_plan_views(
    session: AsyncSession, agent_key: str, *, plan_date: date
) -> list[TradingAgentPlanResponse]:
    """指定日计划视图（批量解析股票名称 + 截至计划日持仓股数标注，D30）。

    主数据缺失为 None，前端回退代号；held_volume 标注「截至计划日持仓」，
    历史计划页不因后续成交失真。
    """
    plans = await list_plans(session, agent_key, plan_date=plan_date)
    if not plans:
        return []
    names: dict[str, str] = {}
    codes = sorted({p.stock_code for p in plans})
    if codes:
        rows = await session.execute(
            select(StockBasic.stock_code, StockBasic.stock_name).where(
                StockBasic.stock_code.in_(codes)
            )
        )
        names = {code: name for code, name in rows.all()}
    held = await _held_volumes(session, agent_key, plan_date, codes)
    views: list[TradingAgentPlanResponse] = []
    for plan in plans:
        view = TradingAgentPlanResponse.model_validate(plan)
        view.stock_name = names.get(plan.stock_code)
        view.held_volume = held.get(plan.stock_code)
        views.append(view)
    return views


async def list_plan_dates(session: AsyncSession, agent_key: str) -> list[date]:
    """指定 Agent 已有交易计划的计划日去重清单（升序），日历打点用。"""
    rows = await session.execute(
        select(AgentTradePlan.plan_date)
        .where(AgentTradePlan.agent_key == agent_key)
        .distinct()
    )
    return sorted(rows.scalars().all())


async def cancel_plan(
    session: AsyncSession, agent_key: str, *, plan_id: int
) -> AgentTradePlan:
    """人工取消当日 active 计划（triggered 之后不可取消）。"""
    plan = await session.get(AgentTradePlan, plan_id)
    if plan is None or plan.agent_key != agent_key:
        raise NotFoundError("Trade plan not found")
    if plan.status == "cancelled":
        return plan
    if plan.status != "active":
        raise BadRequestError(f"计划状态为 {plan.status}，不可取消")
    plan.status = "cancelled"
    await session.commit()
    await session.refresh(plan)
    return plan


async def create_plan(
    session: AsyncSession,
    agent_key: str,
    *,
    plan_date: date,
    stock_code: str,
    plan_type: str,
    strategy: str,
    stop_loss: float,
    position_pct: float,
    basis: str,
    buy_zone_low: float | None = None,
    buy_zone_high: float | None = None,
    target_price: float | None = None,
) -> AgentTradePlan:
    """对话内制定交易计划（与 19:30 定时计划同表同状态机，批次 8 共同执行）。

    语义对齐定时 upsert：active 行覆写字段；expired 复活；cancelled /
    triggered 拒绝改写。buy 必须带买点区间，sell 必须带止盈价。
    """
    if plan_type not in PLAN_TYPES:
        raise BadRequestError(f"plan_type 必须为 {'/'.join(PLAN_TYPES)}")
    if plan_type == "buy":
        if buy_zone_low is None or buy_zone_high is None:
            raise BadRequestError("buy 计划必须提供买点区间（buy_zone_low/high）")
    elif target_price is None:
        raise BadRequestError("sell 计划必须提供止盈价（target_price）")
    code = stock_code.strip()
    exists = await session.scalar(
        select(StockBasic.stock_code).where(StockBasic.stock_code == code)
    )
    if exists is None:
        raise NotFoundError(f"股票代码 {code} 不在主数据中")

    plan = await session.scalar(
        select(AgentTradePlan).where(
            AgentTradePlan.agent_key == agent_key,
            AgentTradePlan.plan_date == plan_date,
            AgentTradePlan.stock_code == code,
            AgentTradePlan.plan_type == plan_type,
        )
    )
    if plan is not None and plan.status in ("cancelled", "triggered"):
        raise BadRequestError(f"该标的当日已有 {plan.status} 计划，不可重复制定")

    if plan is None:
        plan = AgentTradePlan(
            agent_key=agent_key,
            plan_date=plan_date,
            stock_code=code,
            plan_type=plan_type,
            status="active",
        )
        session.add(plan)
    plan.strategy = strategy
    plan.buy_zone_low = None if buy_zone_low is None else Decimal(str(buy_zone_low))
    plan.buy_zone_high = None if buy_zone_high is None else Decimal(str(buy_zone_high))
    plan.target_price = None if target_price is None else Decimal(str(target_price))
    plan.stop_loss = Decimal(str(stop_loss))
    plan.position_pct = Decimal(str(position_pct))
    plan.basis = basis
    if plan.status == "expired":
        plan.status = "active"
    await session.commit()
    await session.refresh(plan)
    return plan


async def list_active_selections(
    session: AsyncSession, agent_key: str
) -> list[AgentStockSelection]:
    """指定 Agent 当前 active 选股清单（最新选入日优先），自选页 agent 分组条目。"""
    rows = await session.execute(
        select(AgentStockSelection)
        .where(
            AgentStockSelection.agent_key == agent_key,
            AgentStockSelection.status == "active",
        )
        .order_by(AgentStockSelection.trade_date.desc(), AgentStockSelection.id.asc())
    )
    return list(rows.scalars().all())


async def get_agent_group(
    session: AsyncSession, agent_key: str
) -> AgentGroupView | None:
    """agent 自选分组视图（未生成分组返回 None，由读路径惰性兜底）。"""
    group = await session.scalar(
        select(UserWatchlistGroup).where(
            UserWatchlistGroup.owner_type == "agent",
            UserWatchlistGroup.agent_key == agent_key,
        )
    )
    if group is None:
        return None
    return AgentGroupView(
        group=group, selections=await list_active_selections(session, agent_key)
    )


async def remove_selection_manual(
    session: AsyncSession, agent_key: str, *, selection_id: int
) -> AgentStockSelection:
    """人工移出选股（仅 active 行可移出；按 Agent 生效，次日不重复选入）。"""
    row = await session.get(AgentStockSelection, selection_id)
    if row is None or row.agent_key != agent_key:
        raise NotFoundError("Selection not found")
    if row.status == "removed":
        return row
    from app.core.clock import utc_now

    row.status = "removed"
    row.removed_at = utc_now()
    row.removed_reason = "manual"
    await session.commit()
    await session.refresh(row)
    return row
