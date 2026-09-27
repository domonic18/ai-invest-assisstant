"""财联社电报保留清理器。

每日 04:10（北京时间）删除 180 天前的 ``news_telegraph`` 行（索引
``publish_time DESC`` 命中范围删除），并连带清理 ``news_ai_score``
中 source='telegraph' 的孤儿标注（字符串松耦合关联，无 FK）。
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, cast, delete, select

from app.core.database import AsyncSessionLocal
from app.models.news_ai_score import NewsAiScore
from app.models.news_telegraph import NewsTelegraph
from collector.core.base import BaseCollector, CollectResult, CollectStatus

RETENTION_DAYS = 180


class NewsTelegraphCleanupCollector(BaseCollector):
    """news_telegraph 保留策略执行器。"""

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

        expired_ids = (
            select(cast(NewsTelegraph.cls_msg_id, String))
            .where(NewsTelegraph.publish_time < cutoff)
            .scalar_subquery()
        )

        try:
            async with AsyncSessionLocal() as session:
                score_result = await session.execute(
                    delete(NewsAiScore).where(
                        NewsAiScore.source == "telegraph",
                        NewsAiScore.item_id.in_(expired_ids),
                    )
                )
                telegraph_result = await session.execute(
                    delete(NewsTelegraph).where(
                        NewsTelegraph.publish_time < cutoff
                    )
                )
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

        deleted_scores = int(getattr(score_result, "rowcount", 0) or 0)
        deleted_telegraphs = int(getattr(telegraph_result, "rowcount", 0) or 0)
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_stored=deleted_telegraphs,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "retention_days": retention_days,
                "cutoff": cutoff.isoformat(),
                "deleted_telegraphs": deleted_telegraphs,
                "deleted_scores": deleted_scores,
            },
        )
