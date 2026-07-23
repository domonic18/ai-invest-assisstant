"""Sina index minute K-line collector via akshare.

抓取主要指数 1 分钟线写入 quote_kline_stock_minute 超表，/indices/intraday 分时图
只读该表。新浪接口返回最近约 8 个交易日，运行时只保留目标交易日
（默认当日），每分钟调度幂等 upsert。
"""

import contextlib
import io
from datetime import date, datetime
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from app.core.constants import INDEX_CODES
from collector.core.base import PostgresCollector
from collector.core.parsing import to_float, to_int

_CN_TZ = ZoneInfo("Asia/Shanghai")


class SinaIndexMinuteCollector(PostgresCollector):
    """新浪财经指数分钟线采集器，写入 quote_kline_stock_minute。"""

    table = "quote_kline_stock_minute"
    conflict_key = "stock_code, trade_time"
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_time"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_time", "close"]

    async def collect(
        self,
        symbols: list[str] | None = None,
        trade_date: date | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        target = trade_date or datetime.now(_CN_TZ).date()
        raw: list[dict[str, Any]] = []
        for symbol in symbols or list(INDEX_CODES):
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                df = ak.stock_zh_a_minute(symbol=symbol, period="1", adjust="")
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                trade_time = datetime.strptime(str(row["day"]), "%Y-%m-%d %H:%M:%S")
                if trade_time.date() != target:
                    continue
                raw.append(
                    {
                        "stock_code": symbol,
                        "trade_time": trade_time.replace(tzinfo=_CN_TZ),
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "amount": row.get("amount"),
                    }
                )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "trade_time": raw["trade_time"],
            "open": to_float(raw.get("open")),
            "high": to_float(raw.get("high")),
            "low": to_float(raw.get("low")),
            "close": to_float(raw.get("close")),
            "volume": to_int(raw.get("volume")),
            "amount": to_float(raw.get("amount")),
        }
