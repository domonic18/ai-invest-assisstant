"""订阅关键词命中扫描定时采集器。

每 10 分钟触发（news-subscription-match 任务），调用
``subscription_service.match_pending`` 对水位后的电报做关键词包含匹配，
命中写 ``news_subscription_hit``（幂等，不耗 LLM）。无启用订阅或无新电报 →
SKIPPED；扫描有条目但零命中为 SUCCESS（records=0）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.news import subscription_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class NewsSubscriptionMatchCollector(BaseCollector):
    """订阅命中扫描器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """水位后电报的关键词命中扫描。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                result = await subscription_service.match_pending(session)
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        matched = int(result["matched"])
        scanned = int(result["scanned"])
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if scanned else CollectStatus.SKIPPED,
            items_collected=matched,
            items_stored=matched,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={"matched": matched, "scanned": scanned},
        )
