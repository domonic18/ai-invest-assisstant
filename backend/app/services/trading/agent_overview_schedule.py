"""Agent 总览/能力视图的定时任务时刻计算（cron 展开 × 交易日历 × cadence 门控）。

「接下来」与「自动化任务」两张视图共用的确定性机器：croniter 候选展开、
cadence 生成门控（与 spider 生成门控同语义）、collector_log 运行中任务检测。
时刻在后端算好（aware UTC），前端纯渲染。视图组装见 ``agent_overview_service``。
"""

from datetime import date, datetime
from datetime import timezone as dt_timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, utc_now
from app.models.collector_log import CollectorLog
from app.models.collector_task import CollectorTask
from app.models.paper_trade import TradingAgent
from app.schemas.paper_trade import AgentNextTask
from app.services.market import trade_calendar_service
from app.services.trading import agent_review_service

# 总览「接下来」消费的 Agent 定时任务（task_name, 显示名, cadence 注册列）
_OVERVIEW_TASKS: tuple[tuple[str, str, str], ...] = (
    ("agent_daily_plan_1900", "每日选股与交易计划", "plan_cadence"),
    ("paper_trade_review_1610", "模拟盘分层复盘", "review_cadence"),
)

# Agent 能力视图「自动化任务」清单（collector_task 实例名, collector_log 键,
# 显示名（含北京时间排程时刻）, cadence 注册列；sync 为全局任务无 cadence）
_AUTOMATION_TASKS: tuple[tuple[str, str, str, str | None], ...] = (
    ("agent_daily_plan_1900", "agent-daily-plan", "每日选股与交易计划（19:30）", "plan_cadence"),
    ("paper_trade_review_1610", "paper-trade-review", "模拟盘分层复盘（19:00）", "review_cadence"),
    ("paper_trade_sync_1600", "paper-trade-sync", "模拟盘盘后同步（16:00）", None),
)

# cadence 门控下 cron 候选扫描上限（月频最坏 ~23 个工作日候选）
_CRON_MAX_CANDIDATES = 40

# 总览运行态判定的两个 agent 定时任务 collector_log 键（与 _AUTOMATION_TASKS log 键一致；
# spider 串行多 Agent 循环只落全局一条 log，working 判定为近似——未来写 meta.agent_key 可精确）
_RUNNING_LOG_KEYS: tuple[str, ...] = ("agent-daily-plan", "paper-trade-review")


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


async def _next_task_times(
    session: AsyncSession, row: TradingAgent
) -> list[AgentNextTask]:
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


async def _running_log_tasks(session: AsyncSession) -> set[str]:
    """collector_log 最新一条处于 running/pending 的任务键集（按 task_name 分组取最新 id）。"""
    latest_ids = (
        (
            await session.execute(
                select(func.max(CollectorLog.id))
                .where(CollectorLog.task_name.in_(_RUNNING_LOG_KEYS))
                .group_by(CollectorLog.task_name)
            )
        )
        .scalars()
        .all()
    )
    if not latest_ids:
        return set()
    rows = (
        await session.execute(
            select(CollectorLog.task_name).where(
                CollectorLog.id.in_(latest_ids),
                CollectorLog.status.in_(("running", "pending")),
            )
        )
    ).all()
    return {str(r[0]) for r in rows}
