"""采集健康检测内部采集器。

每日盘前由 celery beat 触发（collector_task: collector_health_check），
对全部任务实例（task_type × source）执行一次健康判定并把结果 upsert 到
``collector_health_status`` 快照表；页面只读快照，不在请求路径实时判定。

判定与取数逻辑在 ``app/services/collector/health``（纯函数判定器），
本模块只是运行时薄壳。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.clock import today_cn
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class HealthCheckCollector(BaseCollector):
    """采集健康检测器（不采集数据，产出健康快照落库统计）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际逻辑在 ``run`` 中。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        # 函数内导入：health 服务属应用层，collector 运行时延迟依赖，避免导入环
        from app.core.database import AsyncSessionLocal
        from app.services.collector.health.health_service import run_check

        started_at = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            summary = await run_check(session)

        status = CollectStatus.SUCCESS
        errors: list[str] = []
        if summary["failed"] > 0:
            status = CollectStatus.PARTIAL
            errors = [
                f"{summary['failed']} 个实例健康判定失败（详见日志）"
            ]
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=status,
            errors=errors,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "trade_date": today_cn().isoformat(),
                "checked_at": summary["checked_at"],
                "instances": summary["total"],
                "status_counts": summary["status_counts"],
            },
        )
