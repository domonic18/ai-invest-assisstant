"""EastMoney individual stock fund flow collector via akshare."""

from datetime import date
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import clean_stock_code, parse_cn_amount, to_float


class EastMoneyFundFlowCollector(PostgresCollector):
    """东方财富个股资金流向数据采集器（最新交易日全市场快照）。"""

    table = "fund_flow"
    conflict_key = "stock_code, trade_date"
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_date"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_date"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")

    async def collect(
        self, symbols: list[str | dict[str, str]] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        df = ak.stock_fund_flow_individual()
        trade_date = date.today()
        raw: list[dict[str, Any]] = []

        # Normalize requested symbols to plain 6-digit codes.
        requested: set[str] | None = None
        if symbols:
            requested = set()
            for symbol in symbols:
                if isinstance(symbol, str):
                    requested.add(clean_stock_code(symbol))
                else:
                    requested.add(clean_stock_code(symbol["stock"]))

        for _, row in df.iterrows():
            stock_code = str(row["股票代码"]).zfill(6)
            if requested and stock_code not in requested:
                continue
            raw.append(
                {
                    "stock_code": stock_code,
                    "trade_date": trade_date,
                    "main_net_inflow": row["净额"],
                    "super_large_net": None,
                    "large_net": None,
                    "medium_net": None,
                    "small_net": None,
                }
            )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "trade_date": raw["trade_date"],
            "main_net_inflow": parse_cn_amount(raw.get("main_net_inflow")),
            "super_large_net": to_float(raw.get("super_large_net")),
            "large_net": to_float(raw.get("large_net")),
            "medium_net": to_float(raw.get("medium_net")),
            "small_net": to_float(raw.get("small_net")),
        }
