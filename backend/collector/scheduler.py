"""Local collector scheduler based on APScheduler.

Reads active schedules from `collector_task` table and runs collectors locally.
Useful for development environments without SCF.
"""

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from collector.settings import settings
from collector.tasks import collect_auction, collect_fund_flow, collect_kline, collect_news

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TASK_MAP = {
    "kline": lambda: collect_kline(),
    "auction": collect_auction,
    "fund_flow": collect_fund_flow,
    "fund-flow": collect_fund_flow,
    "news": collect_news,
}


async def _load_schedules() -> list[dict[str, Any]]:
    """从 collector_task 表加载启用的调度配置。"""
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT task_name, task_type, schedule
                FROM collector_task
                WHERE is_active = TRUE
                """
            )
        )
        rows = result.mappings().all()
    await engine.dispose()
    return [dict(row) for row in rows]


async def _run_task(task_name: str) -> None:
    """运行单个采集任务。"""
    logger.info("Running scheduled task: %s", task_name)
    task_type = task_name.rsplit("_", 1)[-1]
    coro = TASK_MAP.get(task_type)
    if coro is None:
        logger.warning("No handler for task type: %s", task_type)
        return

    try:
        result = await coro()
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


async def start_scheduler() -> None:
    """启动本地调度器。"""
    schedules = await _load_schedules()
    if not schedules:
        logger.warning("No active collector schedules found")
        return

    scheduler = AsyncIOScheduler()
    for row in schedules:
        task_name = row["task_name"]
        schedule_expr = row["schedule"]
        try:
            trigger = CronTrigger(**_parse_cron(schedule_expr))
        except ValueError as exc:
            logger.warning("Invalid schedule for %s: %s", task_name, exc)
            continue

        scheduler.add_job(
            _run_task,
            trigger=trigger,
            args=[task_name],
            id=task_name,
            replace_existing=True,
        )
        logger.info("Scheduled %s with cron: %s", task_name, schedule_expr)

    scheduler.start()
    logger.info("Collector scheduler started")


def main() -> None:
    """本地调度器入口。"""
    asyncio.run(start_scheduler())


if __name__ == "__main__":
    main()
