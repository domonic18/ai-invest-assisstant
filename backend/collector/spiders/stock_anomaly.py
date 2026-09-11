"""个股异动检测定时采集器（两段式管线的数据获取端）。

17:00 触发：先直采新浪全市场快照（含换手率，akshare 的 ``stock_zh_a_spot``
会丢弃该列），初筛候选后逐股拉新浪日 K 供服务层精算 MA60/量价维度，落
``market_anomaly_stock``。全市场快照缺失抛
:class:`AnomalyInputNotReadyError` 由 Celery 任务退避重试
（docs/arch/08-anomaly-analysis.md §3/§5）。
"""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
import structlog

from app.core.database import AsyncSessionLocal
from app.services.market import stock_anomaly_service
from app.services.market.anomaly_common import AnomalyInputNotReadyError
from collector.core.async_helpers import run_in_thread
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day
from collector.spiders.anomaly_tail import run_attribution_tail

logger = structlog.get_logger(__name__)

_MARKET_SPOT_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData"
)
_NODE = "hs_a"
_PAGE_SIZE = 100
_MAX_PAGES = 120
# 精算需 61 根交易日 K 线（≈90 日历天），留足节假日余量
_KLINE_LOOKBACK_DAYS = 200
# 精算窗口：MA60 + 昨日对照 + 余量
_KLINE_TAIL_BARS = 70
_SPOT_TIMEOUT_SECONDS = 15

_FLOAT_PARAMS = (
    "screen_change_pct",
    "screen_turnover_pct",
    "price_move_pct",
    "volume_ratio",
    "turnover_pct",
    "breakout_volume_ratio",
)


def _params_from_config(config: dict[str, Any]) -> stock_anomaly_service.StockDetectionParams:
    """任务 config_params（未配置时为 None）覆盖服务层默认阈值。"""
    overrides: dict[str, Any] = {
        key: float(config[key]) for key in _FLOAT_PARAMS if config.get(key) is not None
    }
    for key in ("screen_candidate_cap", "attribution_top_n"):
        if config.get(key) is not None:
            overrides[key] = int(config[key])
    return replace(stock_anomaly_service.DEFAULT_STOCK_PARAMS, **overrides)


def _fetch_market_spot_sync() -> list[dict[str, Any]]:
    """分页拉取全市场 A 股快照（同步阻塞，调用方需在线程中执行）。

    只保留检测所需字段；换手率列 ``turnoverratio`` 为初筛网的关键输入。
    """
    rows: list[dict[str, Any]] = []
    page = 1
    while page <= _MAX_PAGES:
        params: dict[str, Any] = {
            "page": page,
            "num": _PAGE_SIZE,
            "sort": "symbol",
            "asc": 1,
            "node": _NODE,
            "symbol": "",
            "_s_r_a": "page",
        }
        response = requests.get(
            _MARKET_SPOT_URL,
            params=params,
            timeout=_SPOT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        for item in batch:
            rows.append(
                {
                    "stock_code": str(item.get("code", "")),
                    "sina_symbol": str(item.get("symbol", "")),
                    "stock_name": str(item.get("name", "")),
                    "close": _to_float(item.get("trade")),
                    "change_pct": _to_float(item.get("changepercent")),
                    "volume": _to_float(item.get("volume")),
                    "amount": _to_float(item.get("amount")),
                    "turnover_rate": _to_float(item.get("turnoverratio")),
                }
            )
        if len(batch) < _PAGE_SIZE:
            break
        page += 1
    return rows


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


async def _fetch_market_spot() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = await run_in_thread(_fetch_market_spot_sync)
    if not rows:
        raise AnomalyInputNotReadyError
    return rows


def _make_kline_fetcher(end_date: date) -> Any:
    """构造逐候选拉日 K 的注入函数（升序 bars，失败返回 None 不阻断整批）。"""

    async def _fetch_kline(sina_symbol: str) -> list[dict[str, Any]] | None:
        def _load() -> list[dict[str, Any]]:
            import akshare as ak  # type: ignore[import-untyped]

            start = (end_date - timedelta(days=_KLINE_LOOKBACK_DAYS)).strftime("%Y%m%d")
            frame = ak.stock_zh_a_daily(
                symbol=sina_symbol, start_date=start, end_date=end_date.strftime("%Y%m%d")
            )
            if frame is None or frame.empty:
                return []
            bars: list[dict[str, Any]] = []
            for _, row in frame.iterrows():
                bars.append(
                    {
                        "date": row.get("date"),
                        "close": _to_float(row.get("close")),
                        "volume": _to_float(row.get("volume")),
                        "turnover": _to_float(row.get("turnover")),
                    }
                )
            return bars[-_KLINE_TAIL_BARS:]

        try:
            bars: list[dict[str, Any]] = await run_in_thread(_load)
            return bars
        except Exception:  # noqa: BLE001
            logger.warning("stock_anomaly_kline_fetch_failed", symbol=sina_symbol)
            return None

    return _fetch_kline


class StockAnomalyCollector(BaseCollector):
    """个股异动检测器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际检测逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """检测当日个股异动并落库。"""
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
            spot_rows = await _fetch_market_spot()
            params = _params_from_config(self.config)
            async with AsyncSessionLocal() as session:
                rows = await stock_anomaly_service.run_stock_detection(
                    session,
                    trade_date,
                    spot_rows,
                    _make_kline_fetcher(trade_date),
                    params,
                )
        except AnomalyInputNotReadyError:
            # 不吞掉：交给 Celery 任务重试，等待全市场快照可用。
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
            "stock", trade_date, params.attribution_top_n
        )

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=len(spot_rows),
            items_stored=len(rows),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "trade_date": trade_date.isoformat(),
                "spot_rows": len(spot_rows),
                "detected": len(rows),
                "attributed": attributed,
            },
        )
