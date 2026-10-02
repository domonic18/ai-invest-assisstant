"""交易 Agent 总览聚合服务（Agent Hub 总览页数据源，agent-hub-plan.md D24）。

每 Agent 聚合：注册行 profile + 模型显示名（join llm_config）+ 当日计划/
自选/订单计数 + 近期活动（计划生成/触发、复盘生成）+ 下次定时任务时刻
（cron 展开 × 交易日历 × 注册行 plan/review_cadence 门控，D28）。
时刻在后端算好（aware UTC），前端纯渲染。

本模块只保留视图组装：定时任务时刻计算见 ``agent_overview_schedule``，
活动流与计数采集见 ``agent_overview_activity``。
"""

from dataclasses import dataclass
from datetime import date, datetime, time

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, today_cn, utc_now
from app.core.config import get_settings
from app.models.agent_trading import AgentStockSelection, AgentTradePlan
from app.models.collector_log import CollectorLog
from app.models.collector_task import CollectorTask
from app.models.kb import KbSource
from app.models.llm_config import LLMConfig
from app.models.paper_trade import TradingAgent
from app.schemas.paper_trade import (
    AgentActivityItem,
    AgentAutomationTask,
    AgentCapabilityResponse,
    AgentMethodologyView,
    AgentNextTask,
    AgentOverviewItem,
    AgentOverviewResponse,
    AgentRuntimeState,
    AgentSkillFilesResponse,
    TradingAgentProfileResponse,
)
from app.schemas.skill import SkillFile
from app.services.market import trade_calendar_service
from app.services.skill.skill_service import SKILL_TEXT_SUFFIXES
from app.services.trading import agent_registry
from app.services.trading.account_service import resolve_agent_accounts
from app.services.trading.agent_methodology import build_methodology_view
from app.services.trading.agent_overview_activity import (
    _fill_stock_names,
    _memory_counts,
    _order_count_today,
    _plan_activity,
    _plans_created_today,
    _review_activity,
    _review_done_keys,
)
from app.services.trading.agent_overview_schedule import (
    _AUTOMATION_TASKS,
    _cadence_due,
    _next_cron_occurrence,
    _next_task_times,
    _running_log_tasks,
)
from app.services.trading.agent_plan_service import plan_skill_id
from app.skills import get_skill

logger = structlog.get_logger(__name__)


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


@dataclass
class _OverviewCtx:
    """总览聚合预取上下文（get_overview 一次查询、_build_item 逐行消费）。"""

    llm_names: dict[int, str]
    latest_trade_date: date
    day_start_cn: datetime
    accounts: dict[str, str]
    running_tasks: set[str]
    review_done_keys: set[str]


async def _build_item(
    session: AsyncSession,
    row: TradingAgent,
    profile: TradingAgentProfileResponse,
    ctx: _OverviewCtx,
) -> AgentOverviewItem:
    """聚合单个 Agent 总览载荷。

    运行态判定链（D32，顺序短路）：off（未启用，仅占位）→ paused（intraday_paused
    人工冻结，盘中执行短路）→ working（log 运行中且 cadence 今日命中）→
    produced_today（当日已产出计划/复盘）→ idle（待命）。
    """
    plan_count = 0
    selection_count = 0
    order_count = 0
    activity: list[AgentActivityItem] = []
    next_tasks: list[AgentNextTask] = []
    state: AgentRuntimeState = "off"

    if row.status != agent_registry.AGENT_STATUS_ACTIVE:
        label = (
            "未启用 · 规划中"
            if row.status == agent_registry.AGENT_STATUS_PLANNED
            else "未启用"
        )
    else:
        plan_count = int(
            await session.scalar(
                select(func.count())
                .select_from(AgentTradePlan)
                .where(
                    AgentTradePlan.agent_key == row.agent_key,
                    AgentTradePlan.plan_date == ctx.latest_trade_date,
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
        activity = [
            *(await _plan_activity(session, row.agent_key)),
            *(await _review_activity(session, row.agent_key)),
        ]
        activity.sort(key=lambda a: a.occurred_at or utc_now(), reverse=True)
        await _fill_stock_names(session, activity)
        next_tasks = await _next_task_times(session, row)
        order_count = await _order_count_today(
            session, row.agent_key, ctx.day_start_cn
        )

        today = ctx.day_start_cn.date()
        plan_running = (
            "agent-daily-plan" in ctx.running_tasks
            and row.plan_cadence is not None
            and await _cadence_due(session, row.plan_cadence, today)
        )
        review_running = (
            "paper-trade-review" in ctx.running_tasks
            and row.review_cadence is not None
            and await _cadence_due(session, row.review_cadence, today)
        )
        produced = row.agent_key in ctx.review_done_keys or await _plans_created_today(
            session, row.agent_key, ctx.day_start_cn
        )
        if row.intraday_paused:
            state, label = "paused", "已暂停 · 盘中执行关闭"
        elif plan_running:
            state, label = "working", "作业中 · 每日选股计划"
        elif review_running:
            state, label = "working", "作业中 · 盘后复盘"
        elif produced:
            state, label = "produced_today", "今日已产出"
        elif next_tasks:
            hhmm = next_tasks[0].scheduled_at.astimezone(CN_TZ).strftime("%H:%M")
            state, label = "idle", f"待命 · 下次 {hhmm}"
        else:
            state, label = "idle", "待命"

    return AgentOverviewItem(
        profile=profile,
        llm_name=ctx.llm_names.get(row.llm_config_id or -1),
        runtime_state=state,
        state_label=label,
        account_name=ctx.accounts.get(row.agent_key),
        plan_count=plan_count,
        selection_count=selection_count,
        order_count=order_count,
        recent_activity=activity[:5],
        next_tasks=next_tasks,
    )


async def get_overview(session: AsyncSession) -> AgentOverviewResponse:
    """总览页聚合：全部注册 Agent 的介绍卡 + 活动状态 + 运行态。

    运行态预取一次查询（绑定账户名 / collector_log 运行中任务 / 今日复盘
    完成集合），_build_item 逐行消费判定链（D32）。
    """
    rows = await agent_registry.list_agents(session)
    profiles = {r.agent_key: agent_registry.to_view(r) for r in rows}
    llm_names = await _llm_name_map(session, rows)
    latest_trade_date = await trade_calendar_service.resolve_latest_trade_date(session)
    day_start_cn = datetime.combine(today_cn(), time.min).replace(tzinfo=CN_TZ)
    ctx = _OverviewCtx(
        llm_names=llm_names,
        latest_trade_date=latest_trade_date,
        day_start_cn=day_start_cn,
        accounts=await resolve_agent_accounts(session, list(profiles)),
        running_tasks=await _running_log_tasks(session),
        review_done_keys=await _review_done_keys(session, day_start_cn),
    )
    items = [await _build_item(session, row, profiles[row.agent_key], ctx) for row in rows]
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
    await _fill_stock_names(session, activity)

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


async def get_agent_skill_files(
    session: AsyncSession, agent_key: str
) -> AgentSkillFilesResponse:
    """作业技能包可视化（配置页只读，D30）。

    trading 技能不进 skill 表（skill_sync 跳过，广场 API 按可见性 404），
    故直读镜像 ``skills/<skill_id>/`` 目录（读取口径与 ``_builtin_files``
    一致：文本后缀 + 数量/大小上限）；方法论区挂载 KB 知识源可视化。
    """
    row = await agent_registry.get_agent(session, agent_key)
    skill_id = plan_skill_id(agent_key)
    descriptor = get_skill(skill_id)

    settings = get_settings()
    base = settings.skills_dir.resolve()
    root = (base / skill_id).resolve()
    files: list[SkillFile] = []
    if root.is_relative_to(base) and root.is_dir():
        for path in sorted(root.rglob("*")):
            if len(files) >= settings.skill_files_max_count:
                break
            if (
                not path.is_file()
                or path.name.startswith(".")
                or path.suffix.lower() not in SKILL_TEXT_SUFFIXES
            ):
                continue
            data = path.read_bytes()
            if len(data) > settings.skill_file_max_bytes:
                continue
            files.append(
                SkillFile(
                    path=path.relative_to(root).as_posix(),
                    size=len(data),
                    content=data.decode("utf-8", errors="replace"),
                )
            )

    methodology = await build_methodology_view(
        session, source_id=row.methodology_source_id
    )
    return AgentSkillFilesResponse(
        skill_id=skill_id,
        skill_label=descriptor.label if descriptor else skill_id,
        skill_is_shared_default=skill_id == "trading-default",
        files=files,
        methodology=(
            AgentMethodologyView.model_validate(methodology) if methodology else None
        ),
    )
