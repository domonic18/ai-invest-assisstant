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
    TaskSpec(
        name="health-check",
        label="采集健康检测",
        data_type="health_check",
        collectors={
            "internal": "collector.spiders.health_check:HealthCheckCollector",
        },
    ),
)
