"""Local collector scheduler based on APScheduler.

Reads active schedules from `collector_task` table and runs collectors through
the same ``collector.scf_handler._run_task`` entry point used by the SCF handler
and the Redis queue worker, ensuring scheduled and ad-hoc execution share logic.
"""

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from collector.scf_handler import _run_task
from collector.settings import settings
from collector.tasks import TASK_MAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _load_schedules() -> list[dict[str, Any]]:
    """从 collector_task 表加载启用的调度配置。"""
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT task_name, task_type, source, schedule
                FROM collector_task
                WHERE is_active = TRUE
                """
            )
        )
        rows = result.mappings().all()
    await engine.dispose()
    return [dict(row) for row in rows]


async def _run_scheduled_task(task_name: str, source: str | None = None) -> None:
    """Run a single scheduled task through the unified runner."""
    logger.info("Running scheduled task: %s", task_name)
    if task_name not in TASK_MAP:
        logger.warning("Unknown scheduled task type: %s", task_name)
        return

    params: dict[str, Any] = {"task": task_name}
    if source:
        params["preferred_source"] = source

    try:
        result = await _run_task(params)
        logger.info(
            "Task %s finished: status=%s collected=%d stored=%d errors=%d",
            task_name,
            result.status.value,
            result.items_collected,
            result.items_stored,
            len(result.errors),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Task %s failed", task_name)


def _parse_cron(schedule: str) -> dict[str, str]:
    """将 cron 表达式解析为 APScheduler CronTrigger 参数。"""
    parts = schedule.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {schedule}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


async def start_scheduler() -> AsyncIOScheduler:
    """启动本地调度器。"""
    schedules = await _load_schedules()
    scheduler = AsyncIOScheduler()
    for row in schedules:
        task_name = row["task_type"]
        source = row.get("source")
        schedule_expr = row["schedule"]
        if not schedule_expr:
            logger.warning("No schedule for %s, skipping", task_name)
            continue
        try:
            trigger = CronTrigger(**_parse_cron(schedule_expr))
        except ValueError as exc:
            logger.warning("Invalid schedule for %s: %s", task_name, exc)
            continue

        scheduler.add_job(
            _run_scheduled_task,
            trigger=trigger,
            args=[task_name, source],
            id=row["task_name"],
            replace_existing=True,
        )
        logger.info("Scheduled %s with cron: %s", task_name, schedule_expr)

    scheduler.start()
    logger.info("Collector scheduler started")
    return scheduler


def main() -> None:
    """本地调度器入口。"""
    asyncio.run(start_scheduler())


if __name__ == "__main__":
    main()
