"""TongHuaShun K-line collector via akshare."""

from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import to_float, to_int


class ThsKlineCollector(PostgresCollector):
    """同花顺日 K / 分钟 K 数据采集器。"""

    table = "kline_daily"
    conflict_key = "stock_code, trade_date"
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_date"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_date", "close"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.period = config.get("period", "daily")

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="20240101",
                end_date="20251231",
                adjust="qfq",
            )
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": symbol,
                        "trade_date": row["日期"],
                        "open": row["开盘"],
                        "high": row["最高"],
                        "low": row["最低"],
                        "close": row["收盘"],
                        "volume": row["成交量"],
                        "amount": row["成交额"],
                        "amplitude": row["振幅"],
                        "pct_change": row["涨跌幅"],
                        "turnover_rate": row.get("换手率"),
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
