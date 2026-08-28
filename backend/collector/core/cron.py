"""Celery beat 调度器的 cron 表达式解析工具。

这些辅助函数最初属于旧版基于 APScheduler 的采集调度器，之所以保留在独立
模块中，是因为 Celery ``CollectorDatabaseScheduler`` 仍需解析存储在
``collector_task.schedule`` 里的 cron 表达式。
"""

import os
import re
from typing import Any
from zoneinfo import ZoneInfo

# 调度时间按北京时间解释（A 股交易时间），与容器时区无关
SCHEDULER_TZ = ZoneInfo(os.getenv("COLLECTOR_TIMEZONE", "Asia/Shanghai"))

_STEP_ONLY_PATTERN = re.compile(r"^(\d+)/(\d+)$")


def _normalize_cron_field(value: str) -> str:
    """将 ``0/30`` 形式的 cron 字段规范化为 ``*/30``，以兼容 Celery。"""
    match = _STEP_ONLY_PATTERN.match(value)
    if match:
        return f"*/{match.group(2)}"
    return value


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
            values = {_map_value(v) for v in range(int(lo_s), int(hi_s) + 1)}
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
