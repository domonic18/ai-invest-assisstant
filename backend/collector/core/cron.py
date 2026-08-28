"""Celery beat 调度器的 cron 表达式解析工具。

``collector_task.schedule`` 存储标准 cron 表达式，由 Celery
``CollectorDatabaseScheduler`` 解析后构造 Celery ``crontab``。Celery 的
星期数字约定与标准 cron 一致（0/7=周日、1=周一），因此星期字段原样透传；
时区语义由 ``celery_app.conf.timezone``（Asia/Shanghai）统一保证。
"""

import re
from typing import Any

_STEP_ONLY_PATTERN = re.compile(r"^(\d+)/(\d+)$")


def _normalize_cron_field(value: str) -> str:
    """将 ``0/30`` 形式的 cron 字段规范化为 ``*/30``，以兼容 Celery。"""
    match = _STEP_ONLY_PATTERN.match(value)
    if match:
        return f"*/{match.group(2)}"
    return value


def _parse_cron(schedule: str) -> dict[str, Any]:
    """将标准 cron 表达式解析为 Celery ``crontab`` 关键字参数。

    星期字段不做数值转换：标准 cron 与 Celery crontab 的约定一致
    （0/7=周日、1=周一），转换反而会整体偏移一天。
    """
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
