"""模拟盘盘后同步采集器（internal 渠道）。

16:00 清算稳定后拉取掘金仿真当日委托/成交/资金快照，经 ``paper_trade_service``
幂等 upsert 三表。非交易日 / ``paper_trade_url`` 未配置 / 同步锁被占 → SKIPPED
（原因写 ``message``）；sidecar/柜台错误向上传播由 runner 记 FAILED。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.core.exceptions import ConflictError
from app.services.trading import paper_trade_service
from app.services.trading.errors import PaperTradeNotConfiguredError
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day


class PaperTradeSyncCollector(BaseCollector):
    """模拟盘盘后同步（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际同步逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """同步或复用当日的模拟盘委托/成交/资金快照。"""
        started_at = datetime.now(timezone.utc)

        def _result(
            status: CollectStatus,
            message: str | None = None,
            summary: dict[str, Any] | None = None,
        ) -> CollectResult:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=status,
                message=message,
                items_collected=0,
                items_stored=0,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata=summary or {},
            )

        trade_date = kwargs.get("trade_date") or latest_trading_day()
        if not is_trading_day(trade_date):
            return _result(
                CollectStatus.SKIPPED, f"{trade_date.isoformat()} 不是交易日"
            )

        try:
            async with AsyncSessionLocal() as session:
                summary = await paper_trade_service.sync_daily(session, trade_date)
        except PaperTradeNotConfiguredError:
            return _result(
                CollectStatus.SKIPPED, "paper_trade_url 未配置，模拟盘同步禁用"
            )
        except ConflictError as exc:
            # 其他实例持有同步锁，本轮执行是冗余的，按良性跳过处理
            return _result(CollectStatus.SKIPPED, str(exc))
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        stored = int(summary["orders"]) + int(summary["executions"])
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=stored,
            items_stored=stored,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata=summary,
        )
