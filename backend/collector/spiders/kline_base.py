"""K 线采集器共享基类 — sina/ths 等渠道共用表配置与清洗逻辑。

子类只需实现 collect（产出 open/high/low/close/volume/amount/amplitude/
change_pct/turnover_rate 键的原始字典）。
"""

from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import to_float, to_int


class BaseKlineCollector(PostgresCollector):
    """日 K / 分钟 K 采集器基类，按 period 写入 quote_kline_stock_daily / quote_kline_stock_minute。"""

    conflict_key = "stock_code, trade_date"
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_date"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_date", "close"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.period = config.get("period", "daily")
        self.table = "quote_kline_stock_minute" if self.period == "minute" else "quote_kline_stock_daily"
        # 盘中触发的采集会写入半日 bar（成交量/换手率约半日值），声明全列更新让
        # 16:30 定时全量重采覆盖修正，避免残值永久保留；
        # 分钟表无 amplitude/change_pct/turnover_rate 列，更新列按 period 收敛
        self.update_columns = (
            ["open", "high", "low", "close", "volume", "amount"]
            if self.period == "minute"
            else [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "amplitude",
                "change_pct",
                "turnover_rate",
            ]
        )

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
            "change_pct": to_float(raw.get("change_pct")),
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
