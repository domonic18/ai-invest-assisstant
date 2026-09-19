"""知识库物理清理采集器（internal 薄壳，实际逻辑在 cleanup_service）。

每轮：清软删过窗的源/素材、abort 超龄分片会话；deep 孤儿扫描内部有
每日一次 Redis 门控（``*/30 * * * *`` 调度下自然做到每日一次）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.kb import cleanup_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class KbCleanupCollector(BaseCollector):
    """知识库清理任务（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """执行一轮清理（锁互斥，忙时跳过）。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                stats = await cleanup_service.run_cleanup(session, deep=True)
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        if stats.get("skippedBusy"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                errors=["上一轮清理仍在进行（锁占用）"],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        purged = stats.get("purgedMedia", 0) + stats.get("purgedSources", 0)
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if purged else CollectStatus.SKIPPED,
            errors=[] if purged else ["本轮无可清理积压"],
            items_collected=purged,
            items_stored=purged,
            metadata=stats,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
