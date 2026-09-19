"""知识点抽取采集器（internal 薄壳，实际逻辑在 extract_service）。

状态驱动：每轮扫描「转写 done 且未抽取」素材做章节推断 + 滑窗抽取，
无工作可做（含模型未配置/任务锁忙）返回 SKIPPED（良性终态）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.kb import extract_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class KbExtractCollector(BaseCollector):
    """知识点抽取任务（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """抽取一轮（章节推断 + 知识点落库，全局锁互斥）。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                stats = await extract_service.run_extraction(session)
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
                errors=["上一轮抽取仍在进行（锁占用）"],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        if stats.get("noModelConfigured"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                errors=["抽取模型未配置"],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        done = stats.get("chaptersInferred", 0) + stats.get("mediasExtracted", 0)
        if done == 0:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                errors=["没有可抽取素材（转写未完成或已抽取）"],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=stats.get("pointsCreated", 0),
            items_stored=stats.get("pointsCreated", 0),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata=stats,
        )
