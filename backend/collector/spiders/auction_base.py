"""集合竞价采集器共享基类 — sina/ths 等渠道共用表配置与清洗逻辑。

各数据源的五档盘口字段名不同，子类通过 PRICE_KEY 等类属性声明键名
（{i} 为 1-5 的档位序号），transform 由基类统一实现。
"""

from datetime import time
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import parse_date, parse_time, to_float, to_int


class BaseAuctionCollector(PostgresCollector):
    """集合竞价（五档盘口快照）采集器基类，写入 quote_auction_stock。"""

    table = "quote_auction_stock"
    conflict_key = "stock_code, trade_date, match_time"
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_date", "match_time"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_date", "match_time"]

    PRICE_KEY: ClassVar[str]
    VOLUME_KEY: ClassVar[str]
    BID_PRICE_FMT: ClassVar[str]
    BID_VOLUME_FMT: ClassVar[str]
    ASK_PRICE_FMT: ClassVar[str]
    ASK_VOLUME_FMT: ClassVar[str]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.match_time = config.get("match_time", time(9, 25, 0))

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "trade_date": parse_date(raw["trade_date"]),
            "match_time": parse_time(raw["match_time"]),
            "price": to_float(raw.get(self.PRICE_KEY)),
            "volume": to_int(raw.get(self.VOLUME_KEY)),
            "bid_prices": [
                to_float(raw.get(self.BID_PRICE_FMT.format(i=i))) for i in range(1, 6)
            ],
            "bid_volumes": [
                to_int(raw.get(self.BID_VOLUME_FMT.format(i=i))) for i in range(1, 6)
            ],
            "ask_prices": [
                to_float(raw.get(self.ASK_PRICE_FMT.format(i=i))) for i in range(1, 6)
            ],
            "ask_volumes": [
                to_int(raw.get(self.ASK_VOLUME_FMT.format(i=i))) for i in range(1, 6)
            ],
        }
