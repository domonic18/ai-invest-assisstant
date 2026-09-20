"""视频关键帧采集器（internal 薄壳，实际逻辑在 vision_service）。

状态驱动：每轮先为「转写 done 且未选帧」的视频选帧入库，再对 pending 帧
批量 VLM 描述；无工作可做（含模型未配置/任务锁忙）返回 SKIPPED（良性终态）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.kb import vision_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class KbVisionCollector(BaseCollector):
    """视频关键帧任务（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """执行一轮（选帧 + VLM 描述两阶段，全局锁互斥）。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                stats = await vision_service.run_vision(session)
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
                message="上一轮视觉通道仍在进行（锁占用）",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        if stats.get("noModelConfigured"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="视觉模型未配置",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        done = stats.get("mediasFramed", 0) + stats.get("framesDescribed", 0)
        if done == 0:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="没有待处理素材（选帧已完成且无 pending 帧）",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=stats.get("framesCreated", 0) + stats.get("framesDescribed", 0),
            items_stored=stats.get("framesCreated", 0) + stats.get("framesDescribed", 0),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata=stats,
        )
