"""交易日历种子刷新采集器（internal 渠道）。

新浪全量交易日历重建 ``market_trade_calendar`` 种子行（人工覆盖行不回改）。
akshare 拉取失败向上抛由 runner 记 FAILED（D5：日历缺失须告警，不静默）。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.market.trade_calendar_service import regenerate_from_sina
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class TradeCalendarSeedCollector(BaseCollector):
    """交易日历种子刷新（service 持久化，采集器薄包装）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际刷新逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """重建种子日历（缺省当年 + 下一年；years 可传 JSON 数组）。"""
        started_at = datetime.now(timezone.utc)
        years = kwargs.get("years")

        async with AsyncSessionLocal() as session:
            written = await regenerate_from_sina(
                session, [int(y) for y in years] if years else None
            )
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=written,
            items_stored=written,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            message=f"新浪日历种子刷新完成，写入 {written} 行",
        )
