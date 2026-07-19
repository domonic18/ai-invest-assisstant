"""Local collector scheduler based on APScheduler.

Reads active schedules from `collector_task` table and runs collectors through
the same ``collector.scf_handler._run_task`` entry point used by the SCF handler
and the Redis queue worker, ensuring scheduled and ad-hoc execution share logic.
"""

import asyncio
import logging
import os
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from collector.scf_handler import _run_task
from collector.settings import settings
from collector.tasks import TASK_MAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 调度时间按北京时间解释（A 股交易时间），与容器时区无关
SCHEDULER_TZ = ZoneInfo(os.getenv("COLLECTOR_TIMEZONE", "Asia/Shanghai"))


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


def _convert_day_of_week(expr: str) -> str:
    """标准 cron 星期字段（0/7=周日）转 APScheduler 语义（0=周一）。

    支持 *、单值、列表、区间与步长；区间跨周日回绕时展开为显式列表。
    """

    def _map_value(value: int) -> int:
        return (value % 7 - 1) % 7

    def _map_token(token: str) -> str:
        if not token or not token[0].isdigit():
            return token  # * 或 mon-fri 等名称原样保留
        base, _, step = token.partition("/")
        step = f"/{step}" if step else ""
        if "-" in base:
            lo_s, hi_s = base.split("-", 1)
            lo, hi = _map_value(int(lo_s)), _map_value(int(hi_s))
            if lo <= hi:
                return f"{lo}-{hi}{step}"
            # 回绕区间（如 6-1 表示周六到周一）：展开后映射
            values = {
                _map_value(v) for v in range(int(lo_s), int(hi_s) + 1)
            }
            return ",".join(str(v) for v in sorted(values))
        return f"{_map_value(int(base))}{step}"

    return ",".join(_map_token(tok) for tok in expr.split(","))


def _parse_cron(schedule: str) -> dict[str, Any]:
    """将标准 cron 表达式解析为 APScheduler CronTrigger 参数。"""
    parts = schedule.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {schedule}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": _convert_day_of_week(parts[4]),
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
            trigger = CronTrigger(timezone=SCHEDULER_TZ, **_parse_cron(schedule_expr))
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
