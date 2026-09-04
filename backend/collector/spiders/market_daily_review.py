"""大盘综述 AI base 定时生成采集器。

16:30 收盘批数据就绪后由 scheduler 触发，调用 ``market_review_service`` 生成
共享 base 并写入 ``ai_analysis_result``。服务层内置 Redis 分布式锁，保证同一
交易日只有一个实例真正调用 LLM。

输入数据（板块资金/指数K线等）尚未落库时抛出
``ReviewInputDataNotReadyError``，由 Celery 任务按 10 分钟退避重试。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services import review as market_review_service
from app.services.review import ReviewInputDataNotReadyError
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
        started_at = datetime.now(timezone.utc)
        trade_date = kwargs.get("trade_date") or latest_trading_day()

        if not is_trading_day(trade_date):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                errors=[f"{trade_date.isoformat()} 不是交易日"],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        try:
            async with AsyncSessionLocal() as session:
                review = await market_review_service.generate_market_review(
                    session, trade_date=trade_date, regenerate=False
                )
        except ReviewInputDataNotReadyError:
            # 不吞掉：交给 Celery 任务重试，等待收盘批数据落库。
            raise
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if not review.cached else CollectStatus.SKIPPED,
            items_collected=1,
            items_stored=0 if review.cached else 1,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={"trade_date": trade_date.isoformat(), "cached": review.cached},
        )
