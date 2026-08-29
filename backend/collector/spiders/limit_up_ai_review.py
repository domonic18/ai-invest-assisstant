"""涨停板 AI 归因定时生成采集器。

16:30 与大盘复盘同批触发（涨停股池 16:00 落库后），调用
``limit_up_ai_service`` 生成题材分组归因并写入 ``ai_analysis_result``。
已生成（input_hash 命中）→ SKIPPED；涨停池数据尚未落库抛
``ReviewInputDataNotReadyError``，由 Celery 任务按 10 分钟退避重试。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.review import ReviewInputDataNotReadyError, limit_up_ai_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day


class LimitUpAiReviewCollector(BaseCollector):
    """涨停板 AI 归因生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """生成或复用当日的涨停板 AI 归因。"""
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
                cached = await limit_up_ai_service.get_cached_attribution(
                    session, trade_date
                )
                if cached is None:
                    await limit_up_ai_service.generate_attribution(
                        session, trade_date=trade_date, regenerate=False
                    )
        except ReviewInputDataNotReadyError:
            # 不吞掉：交给 Celery 任务重试，等待涨停股池 16:00 批次落库。
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

        generated = cached is None
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if generated else CollectStatus.SKIPPED,
            items_collected=1,
            items_stored=1 if generated else 0,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={"trade_date": trade_date.isoformat(), "cached": not generated},
        )
