"""基于 hq.sinajs.cn 实时买卖盘的新浪集合竞价采集器。"""

from typing import Any, ClassVar

import httpx

from app.core.clock import today_cn
from collector.core.parsing import clean_stock_code
from collector.spiders.auction_base import BaseAuctionCollector


class SinaAuctionCollector(BaseAuctionCollector):
    """新浪财经集合竞价数据采集器（基于实时买卖盘快照）。"""

    DEFAULT_BASE_URL = "https://hq.sinajs.cn"

    PRICE_KEY: ClassVar[str] = "current"
    VOLUME_KEY: ClassVar[str] = "volume"
    BID_PRICE_FMT: ClassVar[str] = "buy_{i}_price"
    BID_VOLUME_FMT: ClassVar[str] = "buy_{i}_vol"
    ASK_PRICE_FMT: ClassVar[str] = "sell_{i}_price"
    ASK_VOLUME_FMT: ClassVar[str] = "sell_{i}_vol"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url") or self.DEFAULT_BASE_URL
        self.api_key = config.get("api_key")

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        trade_date = today_cn()

        for symbol in symbols:
            snapshot = await self._fetch_snapshot(symbol)
            snapshot["stock_code"] = symbol
            snapshot["trade_date"] = trade_date
            snapshot["match_time"] = self.match_time
            raw.append(snapshot)

        return raw

    async def _fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        """抓取新浪实时快照并解析五档盘口。"""
        sina_symbol = self._to_sina_symbol(symbol)
        url = f"{self.base_url.rstrip('/')}/list={sina_symbol}"
        headers = {"Referer": "https://finance.sina.com.cn"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
        response.encoding = "GB18030"
        text = response.text

        try:
            payload = text.split('"')[1]
        except IndexError as exc:
            raise ValueError(
                f"Unexpected Sina response for {symbol}: {text[:200]}"
            ) from exc

        parts = payload.split(",")
        # 新浪盘后返回 33 字段的短快照，盘中返回更长快照；只需 0-5 与 8-29 下标。
        if len(parts) < 30:
            raise ValueError(f"Incomplete Sina snapshot for {symbol}: {parts}")

        # 新浪字段顺序：
        # 0 name, 1 open, 2 prev_close, 3 current, 4 high, 5 low,
        # 6 bid1_price, 7 ask1_price, 8 volume, 9 amount,
        # 10 buy1_vol, 11 buy1_price, 12 buy2_vol, 13 buy2_price, ...
        def _part(idx: int) -> str | None:
            return parts[idx] if idx < len(parts) else None

        snapshot: dict[str, Any] = {
            "name": parts[0],
            "open": parts[1],
            "prev_close": parts[2],
            "current": parts[3],
            "high": parts[4],
            "low": parts[5],
            "volume": parts[8],
            "amount": parts[9],
        }
        for i in range(1, 6):
            snapshot[f"buy_{i}_vol"] = _part(10 + (i - 1) * 2)
            snapshot[f"buy_{i}_price"] = _part(11 + (i - 1) * 2)
            snapshot[f"sell_{i}_vol"] = _part(20 + (i - 1) * 2)
            snapshot[f"sell_{i}_price"] = _part(21 + (i - 1) * 2)

        return snapshot

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        """将 6 位股票代码转换为 Sina 格式（sh/sz）。"""
        code = clean_stock_code(symbol)
        prefix = "sh" if code.startswith("6") else "sz"
        return f"{prefix}{code}"
