"""大盘综述 AI base 定时生成采集器。

16:00 收盘后由 scheduler 触发，调用 ``market_review_service`` 生成共享 base
并写入 ``ai_analysis_result``。服务层内置 Redis 分布式锁，保证同一交易日
只有一个实例真正调用 LLM。
"""

from datetime import datetime
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services import market_review_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day


class MarketDailyReviewCollector(BaseCollector):
    """大盘综述 AI base 生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """生成或复用当日的 AI 大盘综述 base。"""
        started_at = datetime.utcnow()
        trade_date = kwargs.get("trade_date") or latest_trading_day()

        if not is_trading_day(trade_date):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                errors=[f"{trade_date.isoformat()} 不是交易日"],
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )

        try:
            async with AsyncSessionLocal() as session:
                review = await market_review_service.generate_market_review(
                    session, trade_date=trade_date, regenerate=False
                )
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if not review.cached else CollectStatus.SKIPPED,
            items_collected=1,
            items_stored=0 if review.cached else 1,
            started_at=started_at,
            finished_at=datetime.utcnow(),
            metadata={"trade_date": trade_date.isoformat(), "cached": review.cached},
        )
