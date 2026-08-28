"""基于 akshare 的新浪 K 线采集器。"""

from typing import Any

from collector.core.parsing import clean_stock_code
from collector.spiders.kline_base import BaseKlineCollector


class SinaKlineCollector(BaseKlineCollector):
    """新浪财经日 K / 分钟 K 数据采集器。"""

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            sina_symbol = self._to_sina_symbol(symbol)
            if self.period == "minute":
                df = ak.stock_zh_a_minute(symbol=sina_symbol, period="1")
                date_col = "day"
            else:
                df = ak.stock_zh_a_daily(symbol=sina_symbol)
                date_col = "date"

            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": symbol,
                        "trade_date": row[date_col],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "amount": row.get("amount"),
                        "amplitude": None,
                        "change_pct": None,
                        "turnover_rate": row.get("turnover"),
                    }
                )

        return raw

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        """将 6 位股票代码转换为 Sina 格式（sh/sz）。"""
        code = clean_stock_code(symbol)
        prefix = "sh" if code.startswith("6") else "sz"
        return f"{prefix}{code}"
