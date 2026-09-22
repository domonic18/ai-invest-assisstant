"""技能优化建议生成采集器（internal 薄壳，实际逻辑在 optimization_service）。

按单执行：dispatch 携带 suggestion_id，非 queued 单（已被处理/不存在）
返回 SKIPPED（良性终态）；生成失败透传 FAILED（建议单留错误文本）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.kb import optimization_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class KbSuggestCollector(BaseCollector):
    """技能优化建议单生成任务（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """生成一张建议单（读技能定义 + 检索知识源 → 修改点列表）。"""
        started_at = datetime.now(timezone.utc)
        suggestion_id = int(kwargs.get("suggestion_id") or 0)
        if not suggestion_id:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=["缺少 suggestion_id 参数"],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        try:
            async with AsyncSessionLocal() as session:
                stats = await optimization_service.run_generation(session, suggestion_id)
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        if stats.get("failed"):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(stats.get("error") or "生成失败")],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        if stats.get("notFound") or stats.get("skippedStatus"):
            reason = "建议单不存在" if stats.get("notFound") else (
                f"建议单状态为 {stats.get('skippedStatus')}，非 queued 跳过"
            )
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=reason,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=stats,
            )
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=int(stats.get("suggestions", 0)),
            items_stored=int(stats.get("suggestions", 0)),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata=stats,
        )
