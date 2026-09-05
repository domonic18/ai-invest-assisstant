"""日 K 数据新鲜度校验与自愈采集器。

收盘后数据源（新浪）发布当日 bar 存在滞后，个股/ETF 采集调度无晚间重跑档，
当日 bar 可能最晚要到下个交易日才补上且无人感知。本任务在交易日晚间运行：

1. 以 ``latest_trading_day()`` 为期望日，逐个核对自选股/指数/ETF/A50 是否有
   对应日 K（与采集集同源，符号清单直接复用各采集器的单一真相源）；
2. 缺失则重跑对应采集任务（``symbols`` 收窄到缺失标的，重跑即自愈）并复验；
3. 数据本已齐为 SKIPPED（良性），重跑后仍缺失为 PARTIAL 并在 errors 中列明
   仍缺的代码（如停牌股会持续 PARTIAL，属于正确的可见信号）。

调度走 ``collector_task``（建议交易日 18:30/21:00 两档），天然幂等。
"""

from datetime import date, datetime, time, timezone
from typing import Any

from app.core.clock import now_cn, today_cn
from app.core.constants import INDEX_CODES
from app.core.database import AsyncSessionLocal
from app.repositories.market.kline_repository import has_daily_bar
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import latest_trading_day
from collector.spiders.sina_etf_kline import SinaEtfKlineCollector

A50_CODE = "CN00Y"
# 当日 bar 收盘后存在发布滞后，17:00 前不校验「期望日=今天」的缺口
_PUBLISH_READY_TIME = time(17, 0)

_CHECK_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("index-kline", tuple(INDEX_CODES)),
    ("etf-kline", tuple(SinaEtfKlineCollector.symbols)),
    ("a50-kline", (A50_CODE,)),
)


class KlineFreshnessCollector(BaseCollector):
    """日 K 新鲜度校验器（不直接写表，自愈由重跑对应采集任务完成）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际逻辑在 ``run`` 中。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        started_at = datetime.now(timezone.utc)
        trade_date = latest_trading_day()

        if trade_date == today_cn() and now_cn().time() < _PUBLISH_READY_TIME:
            return self._result(
                CollectStatus.SKIPPED,
                trade_date,
                ["期望日为今天且当前时间早于 17:00，当日 bar 可能尚未发布"],
                {},
                started_at,
            )

        watchlist = await self._watchlist_codes()
        groups: list[tuple[str, tuple[str, ...]]] = [
            ("watchlist-kline-daily", tuple(watchlist)),
            *_CHECK_GROUPS,
        ]

        healed: list[str] = []
        still_missing: list[str] = []
        metadata: dict[str, Any] = {"trade_date": trade_date.isoformat(), "checked": {}}

        async with AsyncSessionLocal() as session:
            missing_by_task = {
                task_name: [
                    code
                    for code in codes
                    if not await has_daily_bar(session, code, trade_date)
                ]
                for task_name, codes in groups
                if codes
            }

        for task_name, missing in missing_by_task.items():
            metadata["checked"][task_name] = {
                "missing": missing,
                "healed": bool(missing),
            }
            if not missing:
                continue
            await self._rerun(task_name, missing)
            async with AsyncSessionLocal() as session:
                unresolved = [
                    code
                    for code in missing
                    if not await has_daily_bar(session, code, trade_date)
                ]
            healed.extend(code for code in missing if code not in unresolved)
            still_missing.extend(unresolved)

        if still_missing:
            status = CollectStatus.PARTIAL
            errors = [
                f"{trade_date.isoformat()} 重跑后仍缺日 K：{', '.join(still_missing)}"
            ]
        elif healed:
            status = CollectStatus.SUCCESS
            errors = []
        else:
            status = CollectStatus.SKIPPED
            errors = []

        return self._result(status, trade_date, errors, metadata, started_at)

    @staticmethod
    async def _watchlist_codes() -> list[str]:
        from collector.spiders.sina_kline import _fetch_watchlist_codes

        return await _fetch_watchlist_codes()

    @staticmethod
    async def _rerun(task_name: str, symbols: list[str]) -> None:
        # 函数内导入：runner 依赖 registry，registry 懒加载本模块，避免导入环
        from collector.runtime.runner import run_task

        await run_task({"task": task_name, "symbols": symbols})

    def _result(
        self,
        status: CollectStatus,
        trade_date: date,
        errors: list[str],
        metadata: dict[str, Any],
        started_at: datetime,
    ) -> CollectResult:
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=status,
            errors=errors,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata=metadata,
        )
