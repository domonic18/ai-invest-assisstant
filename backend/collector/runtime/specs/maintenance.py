"""系统维护任务声明。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="collector-log-cleanup",
        label="采集日志保留清理",
        data_type="system_maintenance",
        collectors={
            "internal": (
                "collector.spiders.collector_log_cleanup:"
                "CollectorLogCleanupCollector"
            ),
        },
    ),
)
