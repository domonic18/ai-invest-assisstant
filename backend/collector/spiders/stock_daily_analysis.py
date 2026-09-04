"""个股每日 AI 分析定时生成采集器。

16:40 收盘批与大盘复盘（16:30）之后由 scheduler 触发，遍历开启 AI 复盘
分组的自选股逐只调用 ``stock_daily_analysis_service`` 生成并写入
``ai_analysis_result``。

单股 K 线/行情未就绪（``ReviewInputDataNotReadyError``）只记录该股并继续；
仅当全部股票未就绪时向外抛出，由 Celery 任务按 10 分钟退避重试。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.review import ReviewInputDataNotReadyError, stock_daily_analysis_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day


class StockDailyAnalysisCollector(BaseCollector):
    """个股每日 AI 分析生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """逐只生成或复用当日自选股 AI 分析。"""
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

        per_stock: dict[str, str] = {}
        try:
            async with AsyncSessionLocal() as session:
                stock_codes = await stock_daily_analysis_service.list_active_watch_stock_codes(
                    session
                )
                if not stock_codes:
                    return CollectResult(
                        source=self.source,
                        data_type=self.data_type,
                        status=CollectStatus.SKIPPED,
                        errors=["没有开启 AI 复盘的自选股分组"],
                        started_at=started_at,
                        finished_at=datetime.now(timezone.utc),
                    )

                for code in stock_codes:
                    try:
                        analysis = await stock_daily_analysis_service.generate_stock_analysis(
                            session, code, trade_date=trade_date, regenerate=False
                        )
                        per_stock[code] = "cached" if analysis.cached else "generated"
                    except ReviewInputDataNotReadyError:
                        per_stock[code] = "not_ready"
                    except Exception as exc:  # noqa: BLE001
                        # 单股失败隔离：回滚污染后继续下一只
                        await session.rollback()
                        per_stock[code] = f"failed: {exc}"

                not_ready = sum(1 for v in per_stock.values() if v == "not_ready")
                if not_ready and not_ready == len(per_stock):
                    # 全部未就绪视为收盘批数据未落库，整体重试而非终态失败
                    raise ReviewInputDataNotReadyError(
                        "全部自选股的 K 线与行情数据尚未就绪"
                    )
        except ReviewInputDataNotReadyError:
            # 全部股票未就绪：整体交给 Celery 重试，等待收盘批数据落库。
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

        generated = sum(1 for v in per_stock.values() if v == "generated")
        cached = sum(1 for v in per_stock.values() if v == "cached")
        failed = sum(1 for v in per_stock.values() if v.startswith("failed"))
        succeeded = generated + cached

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if succeeded >= 1 else CollectStatus.FAILED,
            items_collected=len(per_stock),
            items_stored=generated,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "trade_date": trade_date.isoformat(),
                "stocks": per_stock,
                "generated": generated,
                "cached": cached,
                "not_ready": sum(1 for v in per_stock.values() if v == "not_ready"),
                "failed": failed,
            },
        )
