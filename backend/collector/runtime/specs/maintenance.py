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
    TaskSpec(
        name="kb-cleanup",
        label="知识库物理清理",
        description="清除软删过窗的源/素材（COS 对象 + 行）、abort 超龄分片会话，每日扫描孤儿对象",
        data_type="kb_cleanup",
        collectors={
            "internal": "collector.spiders.kb_cleanup:KbCleanupCollector",
        },
    ),
)
