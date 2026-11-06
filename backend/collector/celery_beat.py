"""从 ``collector_task`` 表读取 cron 调度配置的 Celery Beat 调度器。

它取代了旧版采集 worker 使用的进程内 APScheduler，既保留管理端 UI 的唯一
真相源（``collector_task.schedule``），又让定时任务获得与临时任务一致的重试、
超时与监控能力。
"""

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import structlog
from celery import current_app as celery_app
from celery.beat import ScheduleEntry, Scheduler
from celery.schedules import crontab
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.collector_task import CollectorTask
from collector.celery_app import resolve_task_options
from collector.core.cron import _normalize_cron_field, _parse_cron

logger = structlog.get_logger(__name__)


def _entry_unchanged(
    entry: ScheduleEntry, schedule: crontab, args: tuple[Any, ...], options: dict[str, Any]
) -> bool:
    """entry 的调度定义是否与库中现状一致。

    Args:
        entry: 上一轮加载的调度条目。
        schedule: 本轮解析出的 crontab。
        args: 本轮解析出的任务参数。
        options: 本轮解析出的队列与时限选项。

    Returns:
        调度定义未变时返回 True，可沿用旧条目的运行态。
    """
    # celery 无类型存根：ScheduleEntry 的属性都是 Any，比较结果须显式收敛
    return bool(
        entry.schedule == schedule
        and entry.args == args
        and entry.options == options
    )


class CollectorDatabaseScheduler(Scheduler):
    """从 ``collector_task`` 行加载调度配置的 Beat 调度器。"""

    _loop: asyncio.AbstractEventLoop | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._schedule: dict[str, ScheduleEntry] = {}
        self._last_sync_at: datetime | None = None
        super().__init__(*args, **kwargs)

    def setup_schedule(self) -> None:
        self._load_schedules()

    def sync(self) -> None:
        self._load_schedules()
        logger.info("beat_schedule_synced", entries=len(self._schedule))
        super().sync()

    @property
    def schedule(self) -> Mapping[str, ScheduleEntry]:
        return self._schedule

    @classmethod
    def _ensure_loop(cls) -> asyncio.AbstractEventLoop:
        """返回 beat 进程的持久事件循环，必要时创建。

        每次 sync 都 ``asyncio.run()`` 会销毁再新建循环，而 asyncpg 连接池
        中的连接仍绑定在旧循环上，下一次 sync 复用连接时抛
        ``another operation is in progress`` 导致 beat 崩溃循环。与 worker
        侧 :class:`AsyncTask` 相同，进程内保持一个循环供所有 DB 查询使用。
        """
        if cls._loop is None or cls._loop.is_closed():
            cls._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(cls._loop)
        return cls._loop

    def _load_schedules(self) -> None:
        rows = self._ensure_loop().run_until_complete(self._fetch_active_schedules())
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
            schedule = crontab(
                minute=_normalize_cron_field(cron_params.get("minute", "*")),
                hour=_normalize_cron_field(cron_params.get("hour", "*")),
                day_of_week=_normalize_cron_field(cron_params.get("day_of_week", "*")),
                day_of_month=_normalize_cron_field(cron_params.get("day", "*")),
                month_of_year=_normalize_cron_field(cron_params.get("month", "*")),
            )
            args = (
                {
                    "task": task_type,
                    "task_name": task_name,
                    "preferred_source": source,
                },
            )
            # 与 dispatcher 同源：定时任务同样携带软/硬时限，否则 beat 派发
            # 的消息裸奔（2026-09-23 生产挂死事故根因之一）
            options = resolve_task_options(task_type, source)

            existing = self._schedule.get(entry_id)
            if existing is not None and _entry_unchanged(existing, schedule, args, options):
                # 沿用旧条目：last_run_at 是「本槽位是否已跑过」的唯一记忆，
                # 重建条目会把它重置到 sync 落点；落点恰在槽位分钟内时
                # crontab 判定该槽位未到期，整个槽位当天被跳过
                # （2026-11-06 生产 19:30 槽位 8 个任务全部未派发）。
                new_schedule[entry_id] = existing
                continue

            new_schedule[entry_id] = ScheduleEntry(
                name=entry_id,
                task="collector.celery_tasks.run_collector_task",
                schedule=schedule,
                args=args,
                kwargs={},
                options=options,
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
