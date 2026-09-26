"""每日计划落库（缓存行 + 选股/计划两表 upsert + agent 分组同步）。

由 ``agent_plan_service`` 在 LLM 校验后调用：``persist_cache_row`` 写
``ai_analysis_result`` 缓存行（同日重跑命中即不再调 LLM），``persist_plan``
upsert 两表并同步 agent 自选分组（选入加入 / 未续选 agent 剔除 / 人工移出
按 Agent 生效不重复选入）。状态机字段（cancelled / triggered）不回改。
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trading import AgentStockSelection, AgentTradePlan
from app.repositories.review import ai_analysis_repository
from app.services.trading.agent_plan_schemas import AgentDailyPlanContent


async def _ensure_agent_group(session: AsyncSession, agent_key: str) -> Any:
    """agent 自选分组（owner_type='agent'，每 Agent 一组，user_id=NULL）。"""
    from app.models.watchlist import UserWatchlistGroup

    row = await session.scalar(
        select(UserWatchlistGroup).where(
            UserWatchlistGroup.owner_type == "agent",
            UserWatchlistGroup.agent_key == agent_key,
        )
    )
    if row is not None:
        return row
    row = UserWatchlistGroup(
        user_id=None,
        owner_type="agent",
        agent_key=agent_key,
        name="交易 Agent 自选",
        sort_order=999,
        is_default=False,
        ai_review_enabled=False,
    )
    session.add(row)
    await session.flush()
    return row


async def persist_plan(
    session: AsyncSession,
    *,
    agent_key: str,
    trade_date: date,
    content: AgentDailyPlanContent,
    source_result_id: int,
) -> None:
    """upsert 选股/计划两表 + agent 分组同步（人工移出不覆盖）。"""
    await _ensure_agent_group(session, agent_key)

    selection_ids: dict[str, int] = {}
    for item in content.selections:
        row = await session.scalar(
            select(AgentStockSelection).where(
                AgentStockSelection.agent_key == agent_key,
                AgentStockSelection.trade_date == trade_date,
                AgentStockSelection.stock_code == item.stock_code,
            )
        )
        if row is None:
            row = AgentStockSelection(
                agent_key=agent_key,
                trade_date=trade_date,
                stock_code=item.stock_code,
                reason=item.reason,
                status="active",
            )
            session.add(row)
        else:
            row.reason = item.reason
            row.status = row.status if row.status == "removed" else "active"
            if row.status == "active":
                row.removed_at = None
                row.removed_reason = None
        row.confidence = (
            None if item.confidence is None else Decimal(str(round(item.confidence, 4)))
        )
        row.source_result_id = source_result_id
        await session.flush()
        selection_ids[item.stock_code] = row.id

    # 未续选的既往 active 选股 → agent 剔除（人工移出行不覆盖）
    stale = (
        (
            await session.execute(
                select(AgentStockSelection).where(
                    AgentStockSelection.agent_key == agent_key,
                    AgentStockSelection.status == "active",
                    AgentStockSelection.trade_date < trade_date,
                )
            )
        )
        .scalars()
        .all()
    )
    today_codes = {s.stock_code for s in content.selections}
    from app.core.clock import utc_now

    for row in stale:
        if row.stock_code in today_codes:
            continue
        row.status = "removed"
        row.removed_at = utc_now()
        row.removed_reason = "agent"

    for plan_item in content.plans:
        plan_row = await session.scalar(
            select(AgentTradePlan).where(
                AgentTradePlan.agent_key == agent_key,
                AgentTradePlan.plan_date == trade_date,
                AgentTradePlan.stock_code == plan_item.stock_code,
                AgentTradePlan.plan_type == plan_item.plan_type,
            )
        )
        if plan_row is None:
            plan_row = AgentTradePlan(
                agent_key=agent_key,
                plan_date=trade_date,
                stock_code=plan_item.stock_code,
                plan_type=plan_item.plan_type,
                status="active",
            )
            session.add(plan_row)
        plan_row.strategy = plan_item.strategy
        plan_row.buy_zone_low = (
            None if plan_item.buy_zone_low is None else Decimal(str(plan_item.buy_zone_low))
        )
        plan_row.buy_zone_high = (
            None if plan_item.buy_zone_high is None else Decimal(str(plan_item.buy_zone_high))
        )
        plan_row.target_price = (
            None if plan_item.target_price is None else Decimal(str(plan_item.target_price))
        )
        plan_row.stop_loss = Decimal(str(plan_item.stop_loss))
        plan_row.position_pct = Decimal(str(plan_item.position_pct))
        plan_row.basis = plan_item.basis
        plan_row.raw = content.model_dump(mode="json")
        # 人工 cancelled / 已触发的状态机字段不回改；当日未触发的 expired 可被重新生成复活
        if plan_row.status == "expired":
            plan_row.status = "active"
        if plan_item.plan_type == "buy":
            plan_row.selection_id = (
                selection_ids.get(plan_item.stock_code) or plan_row.selection_id
            )
    await session.commit()


async def persist_cache_row(
    session: AsyncSession,
    *,
    skill_id: str,
    input_hash: str,
    content: AgentDailyPlanContent,
) -> int:
    """写入 LLM 结果缓存行（``ai_analysis_result``），返回行 id 供选股回填。"""
    return await ai_analysis_repository.insert_result(
        session,
        skill_id=skill_id,
        input_hash=input_hash,
        prompt_id=skill_id,
        model=None,
        structured=content.model_dump(mode="json"),
        latency_ms=0,
        status="success",
    )
