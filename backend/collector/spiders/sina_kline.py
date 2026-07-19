"""Sina K-line collector via akshare."""

from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import clean_stock_code, to_float, to_int


class SinaKlineCollector(PostgresCollector):
    """新浪财经日 K / 分钟 K 数据采集器。"""

    conflict_key = "stock_code, trade_date"
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_date"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_date", "close"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.period = config.get("period", "daily")
        self.table = "kline_minute" if self.period == "minute" else "kline_daily"

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
                        "pct_change": None,
                        "turnover_rate": row.get("turnover"),
                    }
                )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "trade_date": raw["trade_date"],
            "open": to_float(raw.get("open")),
            "high": to_float(raw.get("high")),
            "low": to_float(raw.get("low")),
            "close": to_float(raw.get("close")),
            "volume": to_int(raw.get("volume")),
            "amount": to_float(raw.get("amount")),
            "amplitude": to_float(raw.get("amplitude")),
            "pct_change": to_float(raw.get("pct_change")),
            "turnover_rate": to_float(raw.get("turnover_rate")),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        close = item.get("close")
        return (
            item.get("stock_code") is not None
            and item.get("trade_date") is not None
            and close is not None
            and close > 0
        )

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        """将 6 位股票代码转换为 Sina 格式（sh/sz）。"""
        code = clean_stock_code(symbol)
        prefix = "sh" if code.startswith("6") else "sz"
        return f"{prefix}{code}"
