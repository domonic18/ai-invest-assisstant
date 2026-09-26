"""交易 Agent 计划与选股的查询/人工干预服务（批次 7，D17 干预面）。

admin 端点与对话工具共用：当日计划查询（TradingAgent 页「今日交易计划」
区块）、计划人工取消、选股查询（自选页 agent 分组合并视图）与人工移出
（removed_reason='manual'，全局生效、次日不重复选入）。
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.agent_trading import AgentStockSelection, AgentTradePlan
from app.models.stock import StockBasic
from app.models.watchlist import UserWatchlistGroup

AGENT_GROUP_NAME = "交易 Agent"

PLAN_TYPES: tuple[str, ...] = ("buy", "sell")


@dataclass(slots=True)
class AgentGroupView:
    """自选页 agent 分组合并视图：分组行 + active 选股条目。"""

    group: UserWatchlistGroup
    selections: list[AgentStockSelection]


async def list_plans(
    session: AsyncSession, *, plan_date: date
) -> list[AgentTradePlan]:
    """指定计划日的全部计划（前端按状态分色渲染）。"""
    rows = await session.execute(
        select(AgentTradePlan)
        .where(AgentTradePlan.plan_date == plan_date)
        .order_by(AgentTradePlan.id.asc())
    )
    return list(rows.scalars().all())


async def list_plan_dates(session: AsyncSession) -> list[date]:
    """已有交易计划的计划日去重清单（升序），日历打点用。"""
    rows = await session.execute(select(AgentTradePlan.plan_date).distinct())
    return sorted(rows.scalars().all())


async def cancel_plan(session: AsyncSession, *, plan_id: int) -> AgentTradePlan:
    """人工取消当日 active 计划（triggered 之后不可取消）。"""
    plan = await session.get(AgentTradePlan, plan_id)
    if plan is None:
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
    """对话内制定交易计划（与 19:00 定时计划同表同状态机，批次 8 共同执行）。

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
            AgentTradePlan.plan_date == plan_date,
            AgentTradePlan.stock_code == code,
            AgentTradePlan.plan_type == plan_type,
        )
    )
    if plan is not None and plan.status in ("cancelled", "triggered"):
        raise BadRequestError(f"该标的当日已有 {plan.status} 计划，不可重复制定")

    if plan is None:
        plan = AgentTradePlan(
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
    session: AsyncSession,
) -> list[AgentStockSelection]:
    """当前 active 选股清单（最新选入日优先），自选页 agent 分组条目。"""
    rows = await session.execute(
        select(AgentStockSelection)
        .where(AgentStockSelection.status == "active")
        .order_by(AgentStockSelection.trade_date.desc(), AgentStockSelection.id.asc())
    )
    return list(rows.scalars().all())


async def get_agent_group(session: AsyncSession) -> AgentGroupView | None:
    """agent 自选分组视图（未生成分组返回 None，由读路径惰性兜底）。"""
    group = await session.scalar(
        select(UserWatchlistGroup).where(UserWatchlistGroup.owner_type == "agent")
    )
    if group is None:
        return None
    return AgentGroupView(group=group, selections=await list_active_selections(session))


async def remove_selection_manual(
    session: AsyncSession, *, selection_id: int
) -> AgentStockSelection:
    """人工移出选股（仅 active 行可移出；全局生效，次日不重复选入）。"""
    row = await session.get(AgentStockSelection, selection_id)
    if row is None:
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
