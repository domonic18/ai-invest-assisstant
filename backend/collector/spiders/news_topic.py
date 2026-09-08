"""热点主题聚类定时采集器。

盘中 11:35 / 盘后 16:35 双跑（news-topic 任务），调用
``topic_service.build_topics`` 聚类近 24h 高分电报并写当日快照。
skipped=True（锁忙/无候选/同输入已生成/LLM 失败）→ SKIPPED；
仅基础设施异常向上抛由 Celery 退避。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.news import topic_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class NewsTopicCollector(BaseCollector):
    """热点主题快照生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """本轮聚类（session_key 可显式指定，缺省按北京时间自动判定）。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                result = await topic_service.build_topics(
                    session, session_key=kwargs.get("session_key")
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

        topics = int(result["topics"])
        skipped = bool(result["skipped"])
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if topics else CollectStatus.SKIPPED,
            items_collected=topics,
            items_stored=topics,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "session": result["session"],
                "trade_date": result["trade_date"],
                "topics": topics,
                "skipped": skipped,
            },
        )
