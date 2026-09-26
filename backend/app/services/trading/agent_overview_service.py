"""交易 Agent 总览聚合服务（Agent Hub 总览页数据源，agent-hub-plan.md D24）。

每 Agent 聚合：注册行 profile + 模型显示名（join llm_config）+ 当日计划/
自选/订单计数 + 近期活动（计划生成/触发、复盘生成）+ 下次定时任务时刻
（cron 展开 × 交易日历 × 注册行 plan/review_cadence 门控，D28）。
时刻在后端算好（aware UTC），前端纯渲染。
"""

from datetime import date, datetime, time
from datetime import timezone as dt_timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, today_cn, utc_now
from app.models.agent_trading import (
    AgentMemory,
    AgentStockSelection,
    AgentTradePlan,
)
from app.models.ai_analysis_result import AiAnalysisResult
from app.models.collector_log import CollectorLog
from app.models.collector_task import CollectorTask
from app.models.kb import KbSource
from app.models.llm_config import LLMConfig
from app.models.paper_trade import PaperTradeOrder, TradingAgent
from app.schemas.paper_trade import (
    AgentActivityItem,
    AgentAutomationTask,
    AgentCapabilityResponse,
    AgentMemoryCounts,
    AgentNextTask,
    AgentOverviewItem,
    AgentOverviewResponse,
    TradingAgentProfileResponse,
)
from app.services.market import trade_calendar_service
from app.services.trading import agent_registry, agent_review_service
from app.services.trading.account_service import resolve_agent_account
from app.services.trading.agent_plan_service import plan_skill_id
from app.services.trading.agent_review_service import REVIEW_SKILL_ID
from app.services.trading.errors import AgentAccountNotDesignatedError
from app.skills import get_skill

logger = structlog.get_logger(__name__)

# 总览「接下来」消费的 Agent 定时任务（task_name, 显示名, cadence 注册列）
_OVERVIEW_TASKS: tuple[tuple[str, str, str], ...] = (
    ("agent_daily_plan_1900", "每日选股与交易计划", "plan_cadence"),
    ("paper_trade_review_1610", "模拟盘分层复盘", "review_cadence"),
)

# Agent 能力视图「自动化任务」清单（collector_task 实例名, collector_log 键,
# 显示名, cadence 注册列；sync 为全局任务无 cadence）
_AUTOMATION_TASKS: tuple[tuple[str, str, str, str | None], ...] = (
    ("agent_daily_plan_1900", "agent-daily-plan", "每日选股与交易计划", "plan_cadence"),
    ("paper_trade_review_1610", "paper-trade-review", "模拟盘分层复盘", "review_cadence"),
    ("paper_trade_sync_1600", "paper-trade-sync", "模拟盘盘后同步", None),
)

# cadence 门控下 cron 候选扫描上限（月频最坏 ~23 个工作日候选）
_CRON_MAX_CANDIDATES = 40

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


async def _next_cron_occurrence(
    session: AsyncSession, schedule: str, cadence: str | None
) -> datetime | None:
    """cron 展开 × 交易日历 × cadence 门控的下次触发时刻（aware UTC）。

    cadence None = 全局任务不做门控。与 spider 生成门控同语义：daily=下一
    交易日、weekly=周期末交易日、monthly=月末交易日；cron 非法/日历异常
    返回 None 不阻塞视图。
    """
    from croniter import croniter

    base = utc_now().astimezone(CN_TZ).replace(tzinfo=None)
    try:
        it = croniter(schedule, base)
        for _ in range(_CRON_MAX_CANDIDATES):
            cand: datetime = it.get_next(datetime)
            if cadence is None or await _cadence_due(session, cadence, cand.date()):
                return cand.replace(tzinfo=CN_TZ).astimezone(dt_timezone.utc)
    except Exception:  # noqa: BLE001 - cron 非法/日历查询异常不阻塞总览
        return None
    return None


async def _next_task_times(session: AsyncSession, row: TradingAgent) -> list[AgentNextTask]:
    """单 Agent 定时任务的下次触发时刻（cron 展开 × 交易日历 × cadence 门控，aware UTC）。"""
    schedules: dict[str, str] = {
        r.task_name: r.schedule
        for r in (
            await session.scalars(
                select(CollectorTask).where(
                    CollectorTask.task_name.in_([t[0] for t in _OVERVIEW_TASKS]),
                    CollectorTask.is_active.is_(True),
                )
            )
        ).all()
        if r.schedule
    }
    tasks: list[AgentNextTask] = []
    for task_name, label, cadence_field in _OVERVIEW_TASKS:
        schedule = schedules.get(task_name)
        if schedule is None:
            continue
        scheduled = await _next_cron_occurrence(session, schedule, getattr(row, cadence_field))
        if scheduled is not None:
            tasks.append(AgentNextTask(task=label, scheduled_at=scheduled))
    tasks.sort(key=lambda t: t.scheduled_at)
    return tasks


async def _cadence_due(
    session: AsyncSession, cadence: str, day: date
) -> bool:
    """cadence 门控的单日判定（与 spider 生成门控同语义）。"""
    if not await trade_calendar_service.is_trading_day(session, day):
        return False
    if cadence == "weekly":
        return await agent_review_service.is_last_trading_day_of_week(session, day)
    if cadence == "monthly":
        return await agent_review_service.is_last_trading_day_of_month(session, day)
    return True


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
        next_tasks=await _next_task_times(session, row),
    )


async def get_overview(session: AsyncSession) -> AgentOverviewResponse:
    """总览页聚合：全部注册 Agent 的介绍卡 + 活动状态（前端按 status 过滤雷达）。"""
    rows = await agent_registry.list_agents(session)
    profiles = {r.agent_key: agent_registry.to_view(r) for r in rows}
    llm_names = await _llm_name_map(session, rows)
    latest_trade_date = await trade_calendar_service.resolve_latest_trade_date(session)

    items = [
        await _build_item(session, row, profiles[row.agent_key], llm_names, latest_trade_date)
        for row in rows
    ]
    return AgentOverviewResponse(items=items, generated_at=utc_now())


async def _automation_tasks(
    session: AsyncSession, row: TradingAgent
) -> list[AgentAutomationTask]:
    """Agent 自动化任务视图（cron/状态/下次/最近执行；collector_task 实例行 +
    collector_log 最近一次运行）。"""
    task_rows: dict[str, CollectorTask] = {
        r.task_name: r
        for r in (
            await session.scalars(
                select(CollectorTask).where(
                    CollectorTask.task_name.in_([t[0] for t in _AUTOMATION_TASKS])
                )
            )
        ).all()
    }
    items: list[AgentAutomationTask] = []
    for instance, log_key, label, cadence_field in _AUTOMATION_TASKS:
        task_row = task_rows.get(instance)
        cadence = getattr(row, cadence_field) if cadence_field else None
        next_run_at = None
        if task_row is not None and task_row.is_active and task_row.schedule:
            next_run_at = await _next_cron_occurrence(session, task_row.schedule, cadence)
        last = await session.scalar(
            select(CollectorLog)
            .where(CollectorLog.task_name == log_key)
            .order_by(CollectorLog.id.desc())
            .limit(1)
        )
        items.append(
            AgentAutomationTask(
                key=instance,
                label=label,
                cron=task_row.schedule if task_row else None,
                task_active=bool(task_row.is_active) if task_row else False,
                cadence=cadence,
                next_run_at=next_run_at,
                last_run_at=(last.started_at or last.finished_at) if last else None,
                last_status=last.status if last else None,
            )
        )
    return items


async def _memory_counts(session: AsyncSession, agent_key: str) -> AgentMemoryCounts:
    """活跃记忆按类型计数（status='active'）。"""
    counts = AgentMemoryCounts()
    rows = (
        await session.execute(
            select(AgentMemory.mem_type, func.count())
            .where(AgentMemory.agent_key == agent_key, AgentMemory.status == "active")
            .group_by(AgentMemory.mem_type)
        )
    ).all()
    for mem_type, cnt in rows:
        counts.active_total += int(cnt)
        if mem_type == "discipline":
            counts.discipline = int(cnt)
        elif mem_type == "method":
            counts.method = int(cnt)
        elif mem_type == "lesson":
            counts.lesson = int(cnt)
    return counts


async def get_agent_status(
    session: AsyncSession, agent_key: str
) -> AgentCapabilityResponse:
    """Agent 能力/状态视图（详情页工作台右栏，D29）。

    一屏回答「agent 靠什么工作」：人设 + 方法论知识源 + 作业技能
    （trading-<key> 专属或 trading-default 共享兜底）+ 模型 + 活跃记忆 +
    自动化任务 + 近期活动。
    """
    row = await agent_registry.get_agent(session, agent_key)

    llm_name = None
    if row.llm_config_id is not None:
        llm_name = (await _llm_name_map(session, [row])).get(row.llm_config_id)
    methodology_name = None
    if row.methodology_source_id is not None:
        source = await session.get(KbSource, row.methodology_source_id)
        methodology_name = source.name if source else None

    skill_id = plan_skill_id(agent_key)
    descriptor = get_skill(skill_id)

    activity = [
        *(await _plan_activity(session, agent_key)),
        *(await _review_activity(session, agent_key)),
    ]
    activity.sort(key=lambda a: a.occurred_at or utc_now(), reverse=True)

    return AgentCapabilityResponse(
        profile=agent_registry.to_view(row),
        llm_name=llm_name,
        methodology_source_name=methodology_name,
        skill_id=skill_id,
        skill_label=descriptor.label if descriptor else skill_id,
        skill_is_shared_default=skill_id == "trading-default",
        memory_counts=await _memory_counts(session, agent_key),
        automation=await _automation_tasks(session, row),
        recent_activity=activity[:5],
    )
