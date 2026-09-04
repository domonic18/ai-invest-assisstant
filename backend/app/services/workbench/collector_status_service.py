"""采集引擎状态服务：工作台引擎卡的"在不在跑 / 接下来半天跑什么 / 最近跑得怎样"。

正在跑与最近运行取自 collector_log；未来计划由 collector_task 的 cron 计划经
croniter 展开为未来 12 小时内的触发时刻。任务中文名复用 runtime.registry 的
label 声明（管理端任务目录同一真相源），不在此另建映射。
"""

from datetime import datetime, timedelta, timezone

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, now_cn
from app.models.collector_log import CollectorLog
from app.repositories.admin.collector_log_repository import CollectorLogRepository
from app.repositories.admin.collector_task_repository import CollectorTaskRepository
from app.schemas.workbench import (
    CollectorRunItem,
    CollectorStatusResponse,
    CollectorUpcomingItem,
)

_UPCOMING_WINDOW = timedelta(hours=12)
_UPCOMING_LIMIT = 8
_MAX_OCCURRENCES_PER_TASK = 3
_RUNNING_MAX_AGE = timedelta(hours=2)


def _run_item(row: CollectorLog, task_labels: dict[str, str]) -> CollectorRunItem:
    duration = None
    if row.started_at is not None and row.finished_at is not None:
        duration = max(0, int((row.finished_at - row.started_at).total_seconds()))
    return CollectorRunItem(
        task_name=row.task_name,
        task_label=task_labels.get(row.task_name, row.task_name),
        source=row.source,
        status=row.status,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_seconds=duration,
        records_count=row.records_count,
    )


async def get_collector_status(
    session: AsyncSession, now: datetime | None = None
) -> CollectorStatusResponse:
    """汇总采集引擎状态；collector_task.schedule 非法时跳过该任务不拖垮整体。"""
    now = now or now_cn()
    log_repo = CollectorLogRepository(session)
    task_repo = CollectorTaskRepository(session)

    from collector.runtime.registry import TASK_SPECS

    task_labels = {name: spec.label for name, spec in TASK_SPECS.items()}

    running_row = await log_repo.get_latest_running(max_age=_RUNNING_MAX_AGE)
    recent_rows = await log_repo.list_recent_terminal(limit=3)

    upcoming: list[CollectorUpcomingItem] = []
    base = now.replace(tzinfo=None)
    for task in await task_repo.list_active_scheduled():
        if not task.schedule:
            continue
        spec = TASK_SPECS.get(task.task_type)
        label = spec.label if spec else task.task_type
        try:
            it = croniter(task.schedule, base)
        except Exception:
            continue
        for _ in range(_MAX_OCCURRENCES_PER_TASK):
            try:
                nxt = it.get_next(datetime)
            except Exception:
                break
            if nxt - base > _UPCOMING_WINDOW:
                break
            upcoming.append(
                CollectorUpcomingItem(
                    run_at=nxt.replace(tzinfo=CN_TZ).astimezone(timezone.utc),
                    task_name=task.task_name,
                    task_label=label,
                    source=task.source,
                )
            )

    upcoming.sort(key=lambda item: item.run_at)
    return CollectorStatusResponse(
        is_running=running_row is not None,
        running=_run_item(running_row, task_labels) if running_row else None,
        recent_runs=[_run_item(row, task_labels) for row in recent_rows],
        upcoming=upcoming[:_UPCOMING_LIMIT],
    )
