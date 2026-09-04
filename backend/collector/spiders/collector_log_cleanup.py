"""采集执行日志保留清理器。

每日 03:40（北京时间）删除 90 天前的 ``collector_log`` 行（索引
``started_at`` 命中范围删除）。保留窗口与存量清理迁移
（20260904_batch_d_storage_governance.sql）保持一致。
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.models.collector_log import CollectorLog
from collector.core.base import BaseCollector, CollectResult, CollectStatus

RETENTION_DAYS = 90


class CollectorLogCleanupCollector(BaseCollector):
    """collector_log 保留策略执行器。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：清理逻辑在 ``run`` 中执行。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        started_at = datetime.now(timezone.utc)
        retention_days = int(kwargs.get("retention_days") or RETENTION_DAYS)
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    delete(CollectorLog).where(CollectorLog.started_at < cutoff)
                )
                deleted = int(getattr(result, "rowcount", 0) or 0)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_stored=deleted,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "retention_days": retention_days,
                "cutoff": cutoff.isoformat(),
                "deleted": deleted,
            },
        )
