"""交易 Agent 每日选股与交易计划生成采集器（internal 渠道，heavy 队列）。

19:00 串行在 16:00 sync / 16:10 复盘 / 16:30 涨停归因 / ≥17:45 异动之后；
核心输入「当日复盘解读」18:35 才生成。非交易日 / 未指定 agent 账户 /
paper_trade_url 未配置 → SKIPPED（原因写 ``message``）；输入未就绪
（``ReviewInputDataNotReadyError``）不吞掉，交由 Celery 退避重试。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_plan_service
from app.services.trading.agent_plan_service import PlanGenerationLockedError
from app.services.trading.errors import (
    AgentAccountNotDesignatedError,
    PaperTradeNotConfiguredError,
)
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day


class AgentDailyPlanCollector(BaseCollector):
    """每日选股与交易计划生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """生成或复用当日选股与交易计划。"""
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

        try:
            async with AsyncSessionLocal() as session:
                result = await agent_plan_service.generate_daily_plan(
                    session, trade_date=trade_date, regenerate=False
                )
        except ReviewInputDataNotReadyError:
            # 不吞掉：交给 Celery 任务退避重试，等待复盘解读落库。
            raise
        except AgentAccountNotDesignatedError as exc:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=str(exc) or "未指定 agent 专属账户，每日计划未启用",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        except PaperTradeNotConfiguredError as exc:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=str(exc) or "paper_trade_url 未配置，每日计划未启用",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        except PlanGenerationLockedError as exc:
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

        dropped = result.dropped_codes
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=1,
            items_stored=0 if result.cached else 1,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            message="当日已生成（缓存命中）" if result.cached else None,
            metadata={
                "trade_date": trade_date.isoformat(),
                "cached": result.cached,
                "selections": len(result.content.selections),
                "plans": len(result.content.plans),
                **({"dropped_codes": dropped} if dropped else {}),
            },
        )
