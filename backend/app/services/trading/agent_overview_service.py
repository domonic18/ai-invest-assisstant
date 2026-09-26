"""交易 Agent 总览聚合服务（Agent Hub 总览页数据源，agent-hub-plan.md D24）。

每 Agent 聚合：注册行 profile + 模型显示名（join llm_config）+ 当日计划/
自选/订单计数 + 近期活动（计划生成/触发、复盘生成）+ 下次定时任务时刻
（cron 展开 × 交易日历过滤）。时刻在后端算好（aware UTC），前端纯渲染。
"""

from datetime import date, datetime, time
from datetime import timezone as dt_timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, today_cn, utc_now
from app.models.agent_trading import AgentStockSelection, AgentTradePlan
from app.models.ai_analysis_result import AiAnalysisResult
from app.models.collector_task import CollectorTask
from app.models.llm_config import LLMConfig
from app.models.paper_trade import PaperTradeOrder, TradingAgent
from app.schemas.paper_trade import (
    AgentActivityItem,
    AgentNextTask,
    AgentOverviewItem,
    AgentOverviewResponse,
    TradingAgentProfileResponse,
)
from app.services.market import trade_calendar_service
from app.services.trading import agent_registry
from app.services.trading.account_service import resolve_agent_account
from app.services.trading.agent_review_service import REVIEW_SKILL_ID
from app.services.trading.errors import AgentAccountNotDesignatedError

logger = structlog.get_logger(__name__)

# 总览「接下来」消费的 Agent 定时任务（task_name → 显示名，seed 03-seed.sql）
_OVERVIEW_TASKS: dict[str, str] = {
    "agent_daily_plan_1900": "每日选股与交易计划",
    "paper_trade_review_1610": "模拟盘分层复盘",
}

_PLAN_STATUS_TITLE = {
    "active": "待触发",
    "triggered": "已触发下单",
    "cancelled": "已人工取消",
    "expired": "已过期",
}


async def _llm_name_map(
    session: AsyncSession, rows: list[TradingAgent]
) -> dict[int, str]:
    """批量解析注册行引用的模型显示名（未绑定 = 平台默认）。"""
    ids = {row.llm_config_id for row in rows if row.llm_config_id is not None}
    if not ids:
        return {}
    result = await session.execute(
        select(LLMConfig.id, LLMConfig.name).where(LLMConfig.id.in_(ids))
    )
    return {int(r[0]): str(r[1]) for r in result.all()}


async def _next_task_times(session: AsyncSession) -> list[AgentNextTask]:
    """Agent 定时任务的下次触发时刻（cron 展开 + 交易日历过滤，aware UTC）。"""
    from app.services.collector.cron_utils import expand_cron

    rows = (
        await session.scalars(
            select(CollectorTask).where(
                CollectorTask.task_name.in_(_OVERVIEW_TASKS),
                CollectorTask.is_active.is_(True),
            )
        )
    ).all()
    base = utc_now().astimezone(CN_TZ).replace(tzinfo=None)
    tasks: list[AgentNextTask] = []
    for row in rows:
        if not row.schedule:
            continue
        candidates = expand_cron(row.schedule, base)
        if not candidates:
            continue
        chosen = candidates[0]
        for cand in candidates:
            if await trade_calendar_service.is_trading_day(session, cand.date()):
                chosen = cand
                break
        scheduled = chosen.replace(tzinfo=CN_TZ).astimezone(dt_timezone.utc)
        tasks.append(AgentNextTask(task=_OVERVIEW_TASKS[row.task_name], scheduled_at=scheduled))
    tasks.sort(key=lambda t: t.scheduled_at)
    return tasks


async def _plan_activity(
    session: AsyncSession, agent_key: str
) -> list[AgentActivityItem]:
    """近期计划活动（生成 + 触发/取消，created_at 倒序取 5）。"""
    rows = (
        await session.scalars(
            select(AgentTradePlan)
            .where(AgentTradePlan.agent_key == agent_key)
            .order_by(AgentTradePlan.created_at.desc())
            .limit(5)
        )
    ).all()
    return [
        AgentActivityItem(
            kind="plan",
            title=f"{row.stock_code} {row.plan_type} 计划",
            detail=_PLAN_STATUS_TITLE.get(row.status, row.status),
            occurred_at=row.triggered_at or row.created_at,
        )
        for row in rows
    ]


async def _review_activity(
    session: AsyncSession, agent_key: str
) -> list[AgentActivityItem]:
    """近期复盘活动（ai_analysis_result 按 agent_key 结构化过滤取 3）。"""
    rows = (
        await session.scalars(
            select(AiAnalysisResult)
            .where(
                AiAnalysisResult.skill_id == REVIEW_SKILL_ID,
                AiAnalysisResult.status == "success",
                AiAnalysisResult.structured_output["agent_key"].astext == agent_key,
            )
            .order_by(AiAnalysisResult.created_at.desc())
            .limit(3)
        )
    ).all()
    items: list[AgentActivityItem] = []
    for row in rows:
        period = (row.structured_output or {}).get("period", "day")
        items.append(
            AgentActivityItem(
                kind="review",
                title=f"{period} 复盘已生成",
                detail=row.model,
                occurred_at=row.created_at,
            )
        )
    return items


async def _order_count_today(
    session: AsyncSession, agent_key: str, day_start_cn: datetime
) -> int:
    """Agent 账户当日订单数（未绑定账户记 0）。"""
    try:
        account = await resolve_agent_account(session, agent_key)
    except AgentAccountNotDesignatedError:
        return 0
    return int(
        await session.scalar(
            select(func.count())
            .select_from(PaperTradeOrder)
            .where(
                PaperTradeOrder.paper_trade_account_id == account.id,
                PaperTradeOrder.created_at >= day_start_cn,
            )
        )
    )


async def _build_item(
    session: AsyncSession,
    row: TradingAgent,
    profile: TradingAgentProfileResponse,
    llm_names: dict[int, str],
    latest_trade_date: date,
    next_tasks: list[AgentNextTask],
) -> AgentOverviewItem:
    """聚合单个 Agent 的总览载荷（planned 仅 profile + 模型名）。"""
    if row.status != agent_registry.AGENT_STATUS_ACTIVE:
        return AgentOverviewItem(
            profile=profile,
            llm_name=llm_names.get(row.llm_config_id or -1),
        )

    plan_count = int(
        await session.scalar(
            select(func.count())
            .select_from(AgentTradePlan)
            .where(
                AgentTradePlan.agent_key == row.agent_key,
                AgentTradePlan.plan_date == latest_trade_date,
            )
        )
        or 0
    )
    selection_count = int(
        await session.scalar(
            select(func.count())
            .select_from(AgentStockSelection)
            .where(
                AgentStockSelection.agent_key == row.agent_key,
                AgentStockSelection.status == "active",
            )
        )
        or 0
    )
    day_start_cn = datetime.combine(today_cn(), time.min).replace(tzinfo=CN_TZ)
    activity = [
        *(await _plan_activity(session, row.agent_key)),
        *(await _review_activity(session, row.agent_key)),
    ]
    activity.sort(key=lambda a: a.occurred_at or utc_now(), reverse=True)
    return AgentOverviewItem(
        profile=profile,
        llm_name=llm_names.get(row.llm_config_id or -1),
        plan_count=plan_count,
        selection_count=selection_count,
        order_count=await _order_count_today(session, row.agent_key, day_start_cn),
        recent_activity=activity[:5],
        next_tasks=next_tasks,
    )


async def get_overview(session: AsyncSession) -> AgentOverviewResponse:
    """总览页聚合：全部注册 Agent 的介绍卡 + 活动状态。"""
    rows = await agent_registry.list_agents(session)
    profiles = {r.agent_key: agent_registry.to_view(r) for r in rows}
    llm_names = await _llm_name_map(session, rows)
    latest_trade_date = await trade_calendar_service.resolve_latest_trade_date(session)
    next_tasks = await _next_task_times(session)

    items = [
        await _build_item(session, row, profiles[row.agent_key], llm_names, latest_trade_date, next_tasks)
        for row in rows
    ]
    return AgentOverviewResponse(items=items, generated_at=utc_now())
