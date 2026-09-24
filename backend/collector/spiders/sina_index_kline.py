"""基于 akshare 的新浪指数日 K 采集器。"""

from typing import Any

from app.core.constants import INDEX_CODES
from collector.spiders.kline_base import BaseKlineCollector
from collector.spiders.tracked_a_share import fetch_tracked_extra_codes, is_etf_code


class SinaIndexKlineCollector(BaseKlineCollector):
    """新浪财经指数日 K 采集器。

    指数代码（如 sh000001）直接作为 stock_code 写入 quote_kline_stock_daily，
    与个股日 K 同表；指数无换手率/成交额字段，置 None。
    缺省范围 = 四大指数 + 用户自加的非 ETF 跟踪标的。
    新浪指数日线接口返回全历史，天然支持一次性回填与幂等重跑。
    """

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        if symbols is None:
            tracked = await fetch_tracked_extra_codes()
            symbols = [*INDEX_CODES, *(c for c in tracked if not is_etf_code(c))]
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": symbol,
                        "trade_date": row["date"],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "amount": row.get("amount"),
                    }
                )

        return raw
