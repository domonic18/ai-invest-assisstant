"""复盘状态服务：工作台复盘状态卡的引擎侧状态与统计。

"做没做 / 做得怎样"以 collector_log 中 market-daily-review 的运行记录为真相源，
与用户是否已查看/编辑无关；计划时间由 collector_task 的 cron 计划经 croniter 推得。
"""

from datetime import date, datetime, time, timedelta, timezone

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, now_cn
from app.models.collector_log import CollectorLog
from app.repositories.admin.collector_log_repository import CollectorLogRepository
from app.repositories.admin.collector_task_repository import CollectorTaskRepository
from app.schemas.workbench import ReviewDayStatus, ReviewStatusResponse

_REVIEW_TASK = "market-daily-review"
_HISTORY_DAYS = 15
_STRIP_SIZE = 5


def _cn_date(dt: datetime) -> date:
    """UTC 时间戳转北京日历日。"""
    return dt.astimezone(CN_TZ).date()


def _duration_seconds(row: CollectorLog) -> int | None:
    if row.started_at is None or row.finished_at is None:
        return None
    return max(0, int((row.finished_at - row.started_at).total_seconds()))


def _day_status(rows: list[CollectorLog]) -> str:
    """单日聚合状态：有成功即成功，否则有终态失败即失败，running 视为未完成。"""
    statuses = [row.status for row in rows]
    if "success" in statuses:
        return "success"
    if "running" in statuses:
        return "pending"
    if statuses:
        return "failed"
    return "pending"


async def get_review_status(
    session: AsyncSession, now: datetime | None = None
) -> ReviewStatusResponse:
    """汇总复盘引擎状态；无任何运行记录时返回 pending 空态。"""
    now = now or now_cn()
    today = now.date()
    repo = CollectorLogRepository(session)

    since_cn = datetime.combine(
        today - timedelta(days=_HISTORY_DAYS), time.min, tzinfo=CN_TZ
    )
    runs = await repo.list_runs_for_task(_REVIEW_TASK, since=since_cn.astimezone(timezone.utc))

    by_day: dict[date, list[CollectorLog]] = {}
    for row in runs:
        if row.started_at is not None:
            by_day.setdefault(_cn_date(row.started_at), []).append(row)
    day_status = {day: _day_status(rows) for day, rows in by_day.items()}

    strip_days = set(by_day)
    if today.weekday() < 5:
        strip_days.add(today)
    recent_days = [
        ReviewDayStatus(
            trade_date=day, status=day_status.get(day, "pending")  # type: ignore[arg-type]
        )
        for day in sorted(strip_days, reverse=True)[:_STRIP_SIZE]
    ]

    today_rows = by_day.get(today, [])
    today_success = [r for r in today_rows if r.status == "success"]

    def _end_key(row: CollectorLog) -> datetime:
        return row.finished_at or row.started_at or datetime.min.replace(tzinfo=timezone.utc)

    if today_success:
        status = "done"
        latest = max(today_success, key=_end_key)
        generated_at = latest.finished_at
        duration = _duration_seconds(latest)
    elif today_rows and all(r.status == "failed" for r in today_rows):
        status = "failed"
        generated_at = None
        duration = None
    else:
        status = "pending"
        generated_at = None
        duration = None

    streak = 0
    for day in sorted(day_status, reverse=True):
        state = day_status[day]
        if state == "success":
            streak += 1
        elif day == today or day.weekday() >= 5:
            continue
        else:
            break

    month_start = today.replace(day=1)
    month_rows = [
        r for r in runs if r.started_at is not None and _cn_date(r.started_at) >= month_start
    ]
    month_terminal = [r for r in month_rows if r.status in ("success", "failed")]
    month_success_rate = (
        round(sum(r.status == "success" for r in month_terminal) / len(month_terminal) * 100, 1)
        if month_terminal
        else None
    )

    planned_time: str | None = None
    next_run_at: datetime | None = None
    task_repo = CollectorTaskRepository(session)
    for task in await task_repo.list_active_scheduled():
        if task.task_type != _REVIEW_TASK or not task.schedule:
            continue
        try:
            nxt = croniter(task.schedule, now.replace(tzinfo=None)).get_next(datetime)
        except Exception:
            continue
        next_run_at = nxt.replace(tzinfo=CN_TZ).astimezone(timezone.utc)
        planned_time = nxt.strftime("%H:%M")
        break

    return ReviewStatusResponse(
        status=status,  # type: ignore[arg-type]
        trade_date=today,
        generated_at=generated_at,
        duration_seconds=duration,
        planned_time=planned_time,
        next_run_at=next_run_at,
        streak_days=streak,
        month_success_rate=month_success_rate,
        recent_days=recent_days,
    )
