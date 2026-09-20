"""知识库嵌入物化采集器（internal 薄壳，实际逻辑在 index_service）。

状态驱动：默认增量扫描三类脏行（知识点/分段/图片）向量化写回 PG 行内
``embedding`` 列；``force_rebuild`` 参数触发全量重嵌（模型切换后的人工恢复路径）。
无工作可做（含模型未配置/任务锁忙/维度不符）返回 SKIPPED（良性终态）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.kb import index_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class KbIndexCollector(BaseCollector):
    """知识库嵌入物化任务（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际物化逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """执行一轮嵌入物化（增量或全量重嵌，全局锁互斥）。"""
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
                message="上一轮嵌入物化仍在进行（锁占用）",
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
        if stats.get("dimensionMismatch"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=(
                    f"embedding 实测维度 {stats.get('actualDims')} 与列定义 "
                    f"{stats.get('expectedDims')} 不符，请先执行列维度迁移"
                    "（ALTER TYPE halfvec(n) + 索引重建）再勾选 force_rebuild 全量重嵌"
                ),
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        materialized = sum(
            stats.get(key, 0)
            for key in (
                "pointsEmbedded",
                "segmentsEmbedded",
                "imagesEmbedded",
                "pointsCleared",
                "segmentsCleared",
                "imagesCleared",
            )
        )
        if stats.get("failedKinds"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.PARTIAL,
                errors=[f"物化类别失败：{kind}" for kind in stats["failedKinds"]],
                items_collected=materialized,
                items_stored=materialized,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        if not materialized and not stats.get("forceRebuild"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="没有待物化变更（三类脏行均为空）",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=materialized,
            items_stored=materialized,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata=stats,
        )
