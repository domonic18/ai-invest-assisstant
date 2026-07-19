"""TongHuaShun auction data collector via akshare bid/ask snapshot."""

from datetime import date, datetime, time
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import to_float, to_int


class ThsAuctionCollector(PostgresCollector):
    """同花顺集合竞价数据采集器（基于实时买卖盘快照）。"""

    table = "auction_data"
    conflict_key = "stock_code, trade_date, match_time"
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_date", "match_time"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_date", "match_time"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.match_time = config.get("match_time", time(9, 25, 0))

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        trade_date = date.today()

        for symbol in symbols:
            df = ak.stock_bid_ask_em(symbol=symbol)
            data = dict(zip(df["item"], df["value"]))
            data["stock_code"] = symbol
            data["trade_date"] = trade_date
            data["match_time"] = self.match_time
            raw.append(data)

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        trade_date = raw["trade_date"]
        if isinstance(trade_date, str):
            trade_date = datetime.strptime(trade_date, "%Y-%m-%d").date()

        match_time = raw["match_time"]
        if isinstance(match_time, str):
            match_time = datetime.strptime(match_time, "%H:%M:%S").time()

        return {
            "stock_code": str(raw["stock_code"]),
            "trade_date": trade_date,
            "match_time": match_time,
            "price": to_float(raw.get("最新")),
            "volume": to_int(raw.get("总手")),
            "bid_prices": [to_float(raw.get(f"buy_{i}")) for i in range(1, 6)],
            "bid_volumes": [to_int(raw.get(f"buy_{i}_vol")) for i in range(1, 6)],
            "ask_prices": [to_float(raw.get(f"sell_{i}")) for i in range(1, 6)],
            "ask_volumes": [to_int(raw.get(f"sell_{i}_vol")) for i in range(1, 6)],
        }
