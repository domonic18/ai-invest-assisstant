"""从 ``collector_task`` 表读取 cron 调度配置的 Celery Beat 调度器。

它取代了旧版采集 worker 使用的进程内 APScheduler，既保留管理端 UI 的唯一
真相源（``collector_task.schedule``），又让定时任务获得与临时任务一致的重试、
超时与监控能力。
"""

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from celery import current_app as celery_app
from celery.beat import ScheduleEntry, Scheduler
from celery.schedules import crontab
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.collector_task import CollectorTask
from collector.celery_app import resolve_queue
from collector.core.cron import _normalize_cron_field, _parse_cron


class CollectorDatabaseScheduler(Scheduler):
    """从 ``collector_task`` 行加载调度配置的 Beat 调度器。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._schedule: dict[str, ScheduleEntry] = {}
        self._last_sync_at: datetime | None = None
        super().__init__(*args, **kwargs)

    def setup_schedule(self) -> None:
        self._load_schedules()

    def sync(self) -> None:
        self._load_schedules()
        super().sync()

    @property
    def schedule(self) -> Mapping[str, ScheduleEntry]:
        return self._schedule

    def _load_schedules(self) -> None:
        rows = asyncio.run(self._fetch_active_schedules())
        new_schedule: dict[str, ScheduleEntry] = {}

        for row in rows:
            task_name = row["task_name"]
            task_type = row["task_type"]
            source = row.get("source")
            schedule_expr = row.get("schedule")
            if not schedule_expr:
                continue

            try:
                cron_params = _parse_cron(schedule_expr)
            except ValueError:
                continue

            entry_id = f"collector-task-{task_name}"
            queue = resolve_queue(task_type, source)
            new_schedule[entry_id] = ScheduleEntry(
                name=entry_id,
                task="collector.celery_tasks.run_collector_task",
                schedule=crontab(
                    minute=_normalize_cron_field(cron_params.get("minute", "*")),
                    hour=_normalize_cron_field(cron_params.get("hour", "*")),
                    day_of_week=_normalize_cron_field(cron_params.get("day_of_week", "*")),
                    day_of_month=_normalize_cron_field(cron_params.get("day", "*")),
                    month_of_year=_normalize_cron_field(cron_params.get("month", "*")),
                ),
                args=(
                    {
                        "task": task_type,
                        "task_name": task_name,
                        "preferred_source": source,
                    },
                ),
                kwargs={},
                options={"queue": queue},
                app=celery_app,
            )

        self._schedule = new_schedule
        self._last_sync_at = datetime.now(timezone.utc)

    @staticmethod
    async def _fetch_active_schedules() -> list[dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(
                    CollectorTask.task_name,
                    CollectorTask.task_type,
                    CollectorTask.source,
                    CollectorTask.schedule,
                ).where(
                    CollectorTask.is_active.is_(True),
                    CollectorTask.schedule.isnot(None),
                )
            )
            rows = result.mappings().all()
            return [dict(row) for row in rows]
