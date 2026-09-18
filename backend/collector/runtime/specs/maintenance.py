"""系统维护任务声明。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="collector-log-cleanup",
        label="采集日志保留清理",
        description="定期清理过期采集日志，控制表体积",
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
        description="定时巡检各采集任务成功率与数据新鲜度，输出健康报告",
        data_type="health_check",
        collectors={
            "internal": "collector.spiders.health_check:HealthCheckCollector",
        },
    ),
)
