"""基于 akshare 的新浪个股分钟 K 线采集器（stock-minute 盘后校正渠道）。

抓取 1 分钟线写入 quote_kline_stock_minute 超表。腾讯为盘中主渠道（见
tencent_stock_minute），新浪窗口约 8 个交易日保留盘后跨日校正能力——
其首根 bar 有盘后修订前科，不宜盘中使用。运行时只保留目标交易日（默认
当日）；symbols 缺省时取共享默认范围（见 stock_minute_base）。
"""

import contextlib
import io
from datetime import date, datetime
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.spiders.stock_minute_base import (
    CN_TZ,
    fetch_default_codes,
    to_cn_symbol,
    transform_minute_row,
)


class SinaStockMinuteCollector(PostgresCollector):
    """新浪财经个股分钟线采集器，写入 quote_kline_stock_minute。"""

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
        target = trade_date or datetime.now(CN_TZ).date()
        codes = symbols or await fetch_default_codes(target)
        import akshare as ak  # type: ignore[import-untyped]  # 延迟导入：akshare 装载慢

        raw: list[dict[str, Any]] = []
        for code in codes:
            symbol = to_cn_symbol(code)
            if symbol is None:
                continue
            try:
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    df = ak.stock_zh_a_minute(symbol=symbol, period="1", adjust="")
            except Exception:  # noqa: BLE001 - 单票失败不拖垮整批
                continue
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                trade_time = datetime.strptime(str(row["day"]), "%Y-%m-%d %H:%M:%S")
                if trade_time.date() != target:
                    continue
                raw.append(
                    {
                        "stock_code": code,
                        "trade_time": trade_time.replace(tzinfo=CN_TZ),
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
        return transform_minute_row(raw)
