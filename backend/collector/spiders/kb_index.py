"""知识库索引采集器（internal 薄壳，实际逻辑在 index_service）。

状态驱动：默认增量扫描三类脏行（知识点/分段/图片）向量化入 ES；
``force_rebuild`` 参数触发蓝绿全量重建（切模型后指纹不符时的人工恢复路径）。
无工作可做（含模型未配置/任务锁忙/指纹不符）返回 SKIPPED（良性终态）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.kb import index_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class KbIndexCollector(BaseCollector):
    """知识库索引任务（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际索引逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """执行一轮索引构建（增量或蓝绿重建，全局锁互斥）。"""
        started_at = datetime.now(timezone.utc)
        force_rebuild = str(kwargs.get("force_rebuild", "")).lower() in (
            "1",
            "true",
            "yes",
        )
        try:
            async with AsyncSessionLocal() as session:
                stats = await index_service.run_index(
                    session, force_rebuild=force_rebuild
                )
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
                message="上一轮索引构建仍在进行（锁占用）",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        if stats.get("noModelConfigured"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="embedding 模型未配置",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        if stats.get("fingerprintMismatch"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="嵌入模型指纹已变更，请在任务参数勾选 force_rebuild 触发全量重建",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        indexed = sum(
            stats.get(key, 0)
            for key in (
                "pointsIndexed",
                "segmentsIndexed",
                "imagesIndexed",
                "pointsDeleted",
                "segmentsDeleted",
                "imagesDeleted",
            )
        )
        rebuilt = stats.get("rebuildVersion") is not None
        if stats.get("failedKinds"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.PARTIAL,
                errors=[f"索引类别失败：{kind}" for kind in stats["failedKinds"]],
                items_collected=indexed,
                items_stored=indexed,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        if not indexed and not rebuilt:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="没有待索引变更（三类脏行均为空）",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=indexed,
            items_stored=indexed,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata=stats,
        )
