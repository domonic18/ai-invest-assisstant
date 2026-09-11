"""板块异动检测定时采集器。

16:45 触发（板块收盘快照 sector-quote 16:05 批次落库后），调用
``sector_anomaly_service`` 跑三维规则判定并落 ``market_anomaly_sector``；
快照尚未落库抛 :class:`AnomalyInputNotReadyError`，由 Celery 任务按
10 分钟退避重试（docs/arch/08-anomaly-analysis.md §2/§5）。
"""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.market import sector_anomaly_service
from app.services.market.anomaly_common import AnomalyInputNotReadyError
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day
from collector.spiders.anomaly_tail import run_attribution_tail

_FLOAT_PARAMS = ("price_move_pct", "volume_ratio", "sync_ratio")
_INT_PARAMS = ("baseline_days", "attribution_top_n")


def _params_from_config(config: dict[str, Any]) -> sector_anomaly_service.SectorDetectionParams:
    """任务 config_params（未配置时为 None）覆盖服务层默认阈值。"""
    overrides: dict[str, Any] = {
        key: float(config[key]) for key in _FLOAT_PARAMS if config.get(key) is not None
    }
    overrides.update(
        {
            key: int(config[key]) for key in _INT_PARAMS if config.get(key) is not None
        }
    )
    return replace(sector_anomaly_service.DEFAULT_SECTOR_PARAMS, **overrides)


class SectorAnomalyCollector(BaseCollector):
    """板块异动检测器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际检测逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """检测当日板块异动并落库。"""
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
            params = _params_from_config(self.config)
            async with AsyncSessionLocal() as session:
                rows = await sector_anomaly_service.run_sector_detection(
                    session, trade_date, params
                )
        except AnomalyInputNotReadyError:
            # 不吞掉：交给 Celery 任务重试，等待板块快照 16:05 批次落库。
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

        attributed = await run_attribution_tail(
            "sector", trade_date, params.attribution_top_n
        )

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=len(rows),
            items_stored=len(rows),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "trade_date": trade_date.isoformat(),
                "detected": len(rows),
                "attributed": attributed,
            },
        )
