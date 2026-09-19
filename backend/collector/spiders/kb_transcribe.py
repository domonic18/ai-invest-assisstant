"""知识库课程转写采集器（internal 薄壳，实际逻辑在 transcribe_service）。

状态驱动：每轮扫描 ``queued`` 的 video/audio 素材逐集转写（单集互斥锁），
无待处理素材返回 SKIPPED（良性终态，不触发 fallback）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.kb import transcribe_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class KbTranscribeCollector(BaseCollector):
    """课程转写任务（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """消化 queued 队列（单集锁互斥，忙素材跳过）。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                done = await transcribe_service.process_queued(session)
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        if done == 0:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                errors=["没有待转写素材（队列为空或全部忙）"],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=done,
            items_stored=done,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
