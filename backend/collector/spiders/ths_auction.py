"""基于 akshare 买卖盘快照的同花顺集合竞价采集器。"""

from datetime import date
from typing import Any, ClassVar

from collector.spiders.auction_base import BaseAuctionCollector


class ThsAuctionCollector(BaseAuctionCollector):
    """同花顺集合竞价数据采集器（基于实时买卖盘快照）。"""

    PRICE_KEY: ClassVar[str] = "最新"
    VOLUME_KEY: ClassVar[str] = "总手"
    BID_PRICE_FMT: ClassVar[str] = "buy_{i}"
    BID_VOLUME_FMT: ClassVar[str] = "buy_{i}_vol"
    ASK_PRICE_FMT: ClassVar[str] = "sell_{i}"
    ASK_VOLUME_FMT: ClassVar[str] = "sell_{i}_vol"

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        trade_date = date.today()

        for symbol in symbols:
            df = ak.stock_bid_ask_em(symbol=symbol)
            if df is None or df.empty:
                continue
            data = dict(zip(df["item"], df["value"]))
            data["stock_code"] = symbol
            data["trade_date"] = trade_date
            data["match_time"] = self.match_time
            raw.append(data)

        return raw
