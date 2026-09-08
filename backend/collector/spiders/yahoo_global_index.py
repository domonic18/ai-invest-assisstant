"""Yahoo Finance 全球指标历史回填采集器（12 个月日线，幂等 upsert）。

新指标上线时手动触发一次性回填：chart API 无鉴权，收盘值与东财一致。
覆盖 push2delay 无历史 K 线的港美股指数 + 外汇对 + 布油（东财 GC00Y/DXY
历史另有路径，勿混用）。此后由每日实时快照自积累；USDCNY 无东财源、
HSTECH Yahoo 已下线，均靠每日任务重跑本 spider 幂等续期（1y 全量 upsert）。
"""

import time
from datetime import datetime, timezone
from typing import Any, ClassVar

import requests
import structlog

from app.core.constants import GLOBAL_INDEX_CODES
from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.http_client import DEFAULT_USER_AGENT
from collector.core.parsing import to_float, to_int

logger = structlog.get_logger(__name__)

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_RANGE = "1y"
_INTERVAL = "1d"
_ATTEMPTS = 3

# index_code -> Yahoo symbol（回填清单与 GLOBAL_INDEX_CODES 的 yahoo 子集保持一致）。
# ^HSTECH 已 404 delisted、USDCNH=X 仅返回当日 1 bar 无历史：两者历史均靠东财
# 每日快照自积累；外汇 =X、布油 BZ=F 期货连续
YAHOO_SYMBOLS: dict[str, str] = {
    "HSI": "^HSI",
    "HSTECH": "^HSTECH",
    "DJIA": "^DJI",
    "NDX": "^NDX",
    "SPX": "^GSPC",
    "N225": "^N225",
    "USDCNY": "USDCNY=X",
    "USDJPY": "USDJPY=X",
    "USDEUR": "USDEUR=X",
    "B00Y": "BZ=F",
}


def _fetch_chart(symbol: str) -> dict[str, Any] | None:
    """拉取单 symbol 的日线索引数据，瞬时错误重试。"""
    url = _CHART_URL.format(symbol=symbol)
    last_error: Exception | None = None
    for _ in range(_ATTEMPTS):
        try:
            response = requests.get(
                url,
                params={"range": _RANGE, "interval": _INTERVAL},
                headers={"User-Agent": DEFAULT_USER_AGENT},
                timeout=15,
            )
            response.raise_for_status()
            return response.json().get("chart", {}).get("result", [None])[0]
        except (requests.RequestException, ValueError, IndexError) as exc:
            last_error = exc
            time.sleep(1.0)
    assert last_error is not None
    raise last_error


class YahooGlobalIndexCollector(PostgresCollector):
    """Yahoo 全球指数历史回填，写入 quote_global_index_daily。"""

    table = "quote_global_index_daily"
    conflict_key = "index_code, trade_date"
    update_columns: ClassVar[list[str]] = [
        "open",
        "high",
        "low",
        "close",
        "change_pct",
        "volume",
        "amount",
        "source",
    ]
    normalize = False
    key_fields: ClassVar[list[str]] = ["index_code", "trade_date"]
    required_fields: ClassVar[list[str]] = ["index_code", "trade_date", "close"]

    async def collect(
        self,
        symbols: list[str] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        codes = [
            code
            for code in YAHOO_SYMBOLS
            if code in GLOBAL_INDEX_CODES and (not symbols or code in set(symbols))
        ]
        if not codes:
            return []
        return await run_in_thread(self._collect_sync, codes)

    def _collect_sync(self, codes: list[str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        last_error: Exception | None = None
        for code in codes:
            try:
                result = _fetch_chart(YAHOO_SYMBOLS[code])
            except (requests.RequestException, ValueError, IndexError) as exc:
                # Yahoo Edge 限流(429)等单 symbol 异常不拖垮整批：
                # 部分回填优于整体回退实时快照；全失败才向上抛走渠道 fallback
                logger.warning("yahoo_chart_failed", index_code=code, error=str(exc))
                last_error = exc
                continue
            if result is None:
                logger.warning("yahoo_chart_empty", index_code=code)
                continue
            items.extend(self._transform_chart(code, result))
        if not items and last_error is not None:
            raise last_error
        return items

    @staticmethod
    def _transform_chart(code: str, result: dict[str, Any]) -> list[dict[str, Any]]:
        """chart result -> 日线行；close 为 null 的停牌日跳过，涨跌幅顺算。"""
        timestamps: list[int] = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        rows: list[dict[str, Any]] = []
        prev_close: float | None = None
        for i, ts in enumerate(timestamps):
            close = to_float(closes[i]) if i < len(closes) else None
            if close is None:
                continue
            change_pct = (
                round((close - prev_close) / prev_close * 100, 4)
                if prev_close
                else None
            )
            rows.append(
                {
                    "index_code": code,
                    # Yahoo 日线时间戳为交易所当地开盘时刻，换算 UTC 日期不跨日
                    "trade_date": datetime.fromtimestamp(ts, tz=timezone.utc).date(),
                    "open": to_float(opens[i]) if i < len(opens) else None,
                    "high": to_float(highs[i]) if i < len(highs) else None,
                    "low": to_float(lows[i]) if i < len(lows) else None,
                    "close": close,
                    "change_pct": change_pct,
                    "volume": to_int(volumes[i]) if i < len(volumes) else None,
                    "amount": None,
                    "source": "yahoo",
                }
            )
            prev_close = close
        return rows
