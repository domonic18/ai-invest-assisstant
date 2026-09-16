"""抖音大 V 视频采集器（internal 薄壳，委托 collection_service 两阶段落库）。

listing shell 行与逐条转写回写均由 service 持久化（两阶段语义见其模块
docstring）；本类只负责把统计映射为 CollectResult。通道级失败由 service
向上传播，BaseCollector.run 统一转 FAILED（F-MON 告警 + 资讯 Tab 横幅）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.social import collection_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class SocialVideoCollector(BaseCollector):
    """抖音大 V 视频采集器。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际采集逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """两阶段采集：listing shell 行 + 逐条转写回写。"""
        started_at = datetime.now(timezone.utc)
        account_id = kwargs.get("account_id")
        backfill = bool(kwargs.get("backfill", False))
        try:
            async with AsyncSessionLocal() as session:
                stats = await collection_service.collect_all_accounts(
                    session, account_id=account_id, backfill=backfill
                )
        except Exception as exc:  # noqa: BLE001 —— 通道级失败统一 FAILED
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        processed = int(stats["ok"]) + int(stats["degraded"])
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=int(stats["listed"]) + int(stats["resumed"]),
            items_stored=processed,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata=dict(stats),
        )
