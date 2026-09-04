"""基于 akshare 的新浪 ETF 日 K 采集器。"""

from typing import Any, ClassVar

from collector.spiders.kline_base import BaseKlineCollector

_ETF_CODES = ("sh510300",)


class SinaEtfKlineCollector(BaseKlineCollector):
    """新浪财经 ETF 日 K 采集器（沪深300ETF sh510300）。

    ETF 代码直接作为 stock_code 写入 quote_kline_stock_daily，与指数/个股日 K 同表；
    新浪 ETF 日线接口返回全历史，天然支持一次性回填与幂等重跑。
    """

    symbols: ClassVar[tuple[str, ...]] = _ETF_CODES

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        raw: list[dict[str, Any]] = []
        for symbol in symbols or list(self.symbols):
            df = ak.fund_etf_hist_sina(symbol=symbol)
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
