"""盘中执行观测查询服务（批次 8 PR-3：执行动态 Tab 数据面）。

只读消费 ``paper_trade_exec_observation``（PR-1 逐 tick 判断留痕）：
分页条目（服务端解析 decision_answers/market_snapshot JSONB 为结构化
字段，前端零 JSONB 知识）+ 恒全天口径的 summary 计数。显著事件口径 =
L0 非「无动作」或存在抑制原因，由查询参数控制是否过滤。
"""

from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.models.agent_trading import AgentTradePlan
from app.models.paper_trade import PaperTradeExecObservation
from app.models.stock import StockBasic
from app.schemas.paper_trade import (
    TradingAgentObservationDecision,
    TradingAgentObservationItem,
    TradingAgentObservationPage,
    TradingAgentObservationSummary,
)
from app.services.trading import agent_registry

#: 显著事件：L0 非「无动作」或存在抑制原因（执行动态默认过滤口径）
SIGNIFICANT_FILTER = or_(
    PaperTradeExecObservation.l0_verdict != "no_action",
    PaperTradeExecObservation.suppression_reason.is_not(None),
)


async def resolve_observation_date(
    session: AsyncSession, agent_key: str
) -> date | None:
    """最近有观测的交易日（MAX(trade_date)）。"""
    row = await session.execute(
        select(func.max(PaperTradeExecObservation.trade_date)).where(
            PaperTradeExecObservation.agent_key == agent_key
        )
    )
    return row.scalar_one_or_none()


def _to_item(
    row: PaperTradeExecObservation,
    *,
    stock_name: str | None,
    plan_type: str | None,
) -> TradingAgentObservationItem:
    """观测行 → wire 条目（JSONB 逐键安全取值，缺键为 None）。"""
    snapshot = row.market_snapshot or {}
    answers = row.decision_answers or {}
    action_answer = answers.get("action") or {}
    noul_answer = answers.get("noul") or {}
    score_answer = answers.get("score") or {}
    noul = noul_answer.get("noul")

    def _num(key: str, *sources: dict[str, Any]) -> float | None:
        for source in sources:
            value = source.get(key)
            if value is not None:
                return float(value)
        return None

    decision = None
    if row.decision_answers:
        decision = TradingAgentObservationDecision(
            served_model=answers.get("served_model"),
            choice=action_answer.get("choice"),
            confidence=_num("confidence", action_answer),
            noul=bool(noul) if noul is not None else None,
            score=_num("score", score_answer),
            window=snapshot.get("window"),
        )
    volume = snapshot.get("volume")
    return TradingAgentObservationItem(
        id=row.id,
        tick_time=row.tick_time,
        trade_date=row.trade_date,
        agent_key=row.agent_key,
        plan_id=row.plan_id,
        stock_code=row.stock_code,
        stock_name=stock_name,
        plan_type=plan_type,
        price=_num("price", snapshot),
        change_pct=_num("change_pct", snapshot),
        l0_verdict=row.l0_verdict,
        trigger_reason=row.trigger_reason,
        l0_detail=snapshot.get("l0_detail"),
        decision=decision,
        action=row.action,
        suppression_reason=row.suppression_reason,
        is_shadow=row.is_shadow,
        cl_ord_id=snapshot.get("cl_ord_id"),
        order_volume=int(volume) if volume is not None else None,
    )


async def _build_summary(
    session: AsyncSession, agent_key: str, trade_date: date
) -> TradingAgentObservationSummary:
    """全天口径计数：一条 group-by SQL 聚合三组分布（不受 significant 过滤影响）。"""
    rows = await session.execute(
        select(
            PaperTradeExecObservation.l0_verdict,
            PaperTradeExecObservation.action,
            PaperTradeExecObservation.suppression_reason,
            func.count(),
        )
        .where(
            PaperTradeExecObservation.agent_key == agent_key,
            PaperTradeExecObservation.trade_date == trade_date,
        )
        .group_by(
            PaperTradeExecObservation.l0_verdict,
            PaperTradeExecObservation.action,
            PaperTradeExecObservation.suppression_reason,
        )
    )
    summary = TradingAgentObservationSummary()
    for verdict, action, suppression, count in rows.all():
        count = int(count)
        summary.total_ticks += count
        summary.l0_verdict_counts[verdict] = (
            summary.l0_verdict_counts.get(verdict, 0) + count
        )
        if action:
            summary.action_counts[action] = (
                summary.action_counts.get(action, 0) + count
            )
        if suppression:
            summary.suppression_counts[suppression] = (
                summary.suppression_counts.get(suppression, 0) + count
            )
        if verdict != "no_action" or suppression:
            summary.significant_ticks += count
    return summary


async def list_agent_observations(
    session: AsyncSession,
    agent_key: str,
    *,
    trade_date: date | None = None,
    significant_only: bool = True,
    page: int,
    page_size: int,
) -> TradingAgentObservationPage:
    """执行观测分页 + 全天 summary。

    Args:
        agent_key: 交易 Agent 标识（不存在抛 NotFoundError → 404）。
        trade_date: 交易日；缺省解析链 = 最近有观测日（当日有观测即当日，
            无任何观测回退 today_cn，首页空态）。
        significant_only: True 仅显著事件（L0 非无动作或存在抑制原因）。
        page: 页码（1 起）。
        page_size: 每页条数。

    Returns:
        TradingAgentObservationPage：items 按 tick_time 倒序（最新在前），
        summary 恒全天口径。
    """
    await agent_registry.get_agent(session, agent_key)
    resolved = trade_date or await resolve_observation_date(session, agent_key) or today_cn()

    conditions = [
        PaperTradeExecObservation.agent_key == agent_key,
        PaperTradeExecObservation.trade_date == resolved,
    ]
    if significant_only:
        conditions.append(SIGNIFICANT_FILTER)

    total = int(
        await session.scalar(
            select(func.count())
            .select_from(PaperTradeExecObservation)
            .where(*conditions)
        )
        or 0
    )
    rows = list(
        await session.scalars(
            select(PaperTradeExecObservation)
            .where(*conditions)
            .order_by(
                PaperTradeExecObservation.tick_time.desc(),
                PaperTradeExecObservation.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    names: dict[str, str] = {}
    codes = sorted({row.stock_code for row in rows})
    if codes:
        name_rows = await session.execute(
            select(StockBasic.stock_code, StockBasic.stock_name).where(
                StockBasic.stock_code.in_(codes)
            )
        )
        names = {code: name for code, name in name_rows.all()}
    plan_types: dict[int, str] = {}
    plan_ids = sorted({row.plan_id for row in rows if row.plan_id is not None})
    if plan_ids:
        plan_rows = await session.execute(
            select(AgentTradePlan.id, AgentTradePlan.plan_type).where(
                AgentTradePlan.id.in_(plan_ids)
            )
        )
        plan_types = {pid: ptype for pid, ptype in plan_rows.all()}

    return TradingAgentObservationPage(
        trade_date=resolved,
        total=total,
        page=page,
        page_size=page_size,
        items=[
            _to_item(
                row,
                stock_name=names.get(row.stock_code),
                plan_type=plan_types.get(row.plan_id) if row.plan_id else None,
            )
            for row in rows
        ],
        summary=await _build_summary(session, agent_key, resolved),
    )
