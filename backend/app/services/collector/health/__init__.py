"""采集健康监测判定引擎包。

纯函数判定内核（``health_judge``）与 IO 组装（``health_snapshot`` /
``health_service``）完全解耦：二期告警（F-MON-05）复用同一内核加
通知外发即可。本包禁止 import ``collector.runtime``（services 层
不依赖 collector 执行层，避免导入环）。
"""

from app.services.collector.health.error_classifier import (
    CAUSE_LABELS,
    classify_error,
)
from app.services.collector.health.health_judge import (
    JudgeThresholds,
    build_schedule_rows,
    judge_instance,
)
from app.services.collector.health.health_service import (
    clear_snapshots,
    get_channels,
    get_overview,
    get_schedule_check,
    get_tasks,
    run_check,
)
from app.services.collector.health.health_snapshot import build_snapshot

__all__ = [
    "CAUSE_LABELS",
    "JudgeThresholds",
    "build_schedule_rows",
    "build_snapshot",
    "classify_error",
    "clear_snapshots",
    "get_channels",
    "get_overview",
    "get_schedule_check",
    "get_tasks",
    "judge_instance",
    "run_check",
]
