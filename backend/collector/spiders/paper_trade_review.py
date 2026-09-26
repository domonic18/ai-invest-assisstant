"""模拟盘复盘生成采集器（internal 渠道，heavy 队列）。

16:10 串行在盘后同步之后，生成 agent 账户当日分层复盘；周五 / 月末最后一个
交易日（日历判定，cron 表达不了）同任务内加发周度 / 月度——加发失败不影响
日度结果（记入 metadata）。非交易日 / 未指定 agent 账户 / 无复盘对象 →
SKIPPED（原因写 ``message``）；输入未就绪（``ReviewInputDataNotReadyError``）
不吞掉，交由 Celery 退避重试。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_review_service
from app.services.trading.agent_review_service import (
    NoReviewTargetError,
    PaperTradeReviewLockedError,
)
from app.services.trading.errors import AgentAccountNotDesignatedError
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day


class PaperTradeReviewCollector(BaseCollector):
    """模拟盘日/周/月复盘生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """生成或复用当日复盘；周期末加发周/月度。"""
        started_at = datetime.now(timezone.utc)
        trade_date = kwargs.get("trade_date") or latest_trading_day()

        if not is_trading_day(trade_date):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=f"{trade_date.isoformat()} 不是交易日",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        metadata: dict[str, Any] = {"trade_date": trade_date.isoformat()}
        try:
            async with AsyncSessionLocal() as session:
                day = await agent_review_service.generate_review(
                    session, period="day", trade_date=trade_date, regenerate=False
                )
                metadata["day"] = {"cached": day.cached}

                # 周期末日历判定加发（失败不拖垮日度结果）
                for period, checker in (
                    ("week", agent_review_service.is_last_trading_day_of_week),
                    ("month", agent_review_service.is_last_trading_day_of_month),
                ):
                    if not await checker(session, trade_date):
                        continue
                    try:
                        extra = await agent_review_service.generate_review(
                            session,
                            period=period,  # type: ignore[arg-type]
                            trade_date=trade_date,
                            regenerate=False,
                        )
                        metadata[period] = {"cached": extra.cached}
                    except (NoReviewTargetError, PaperTradeReviewLockedError) as exc:
                        metadata[period] = {"skipped": str(exc)}
        except ReviewInputDataNotReadyError:
            # 不吞掉：交给 Celery 任务退避重试，等待盘后同步落库。
            raise
        except AgentAccountNotDesignatedError as exc:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=str(exc) or "未指定 agent 专属账户，复盘未启用",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        except NoReviewTargetError as exc:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=str(exc),
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
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

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=1,
            items_stored=0 if day.cached else 1,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            message="当日已生成（缓存命中）" if day.cached else None,
            metadata=metadata,
        )
