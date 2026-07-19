"""Sina real-time quote collector via akshare.

Fetches A-share spot/quotes for all listed stocks and writes the requested
symbols into Redis as ``quote:{stock_code}`` with a short TTL.  This matches
the storage-layer design where real-time quotes live in the Redis cache tier.
"""

import json
from datetime import datetime
from typing import Any

from collector.core.base import BaseCollector
from collector.core.config import redis_url as default_redis_url
from collector.core.parsing import clean_stock_code, to_float


class SinaQuoteCollector(BaseCollector):
    """新浪财经 A 股实时行情采集器。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._redis_url = config.get("redis_url") or default_redis_url
        self.ttl_seconds = int(config.get("ttl_seconds", 300))

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        df = ak.stock_zh_a_spot()
        if df.empty:
            return []

        requested = None
        if symbols:
            requested = {clean_stock_code(code) for code in symbols}

        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            full_code = str(row["代码"])
            code = clean_stock_code(full_code)
            if requested and code not in requested:
                continue

            raw.append(
                {
                    "stock_code": code,
                    "stock_name": row["名称"],
                    "price": row["最新价"],
                    "change": row["涨跌额"],
                    "pct_change": row["涨跌幅"],
                    "bid": row["买入"],
                    "ask": row["卖出"],
                    "prev_close": row["昨收"],
                    "open": row["今开"],
                    "high": row["最高"],
                    "low": row["最低"],
                    "volume": row["成交量"],
                    "amount": row["成交额"],
                    "timestamp": row["时间戳"],
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "stock_name": str(raw.get("stock_name", "")),
            "price": to_float(raw.get("price")),
            "change": to_float(raw.get("change")),
            "pct_change": to_float(raw.get("pct_change")),
            "bid": to_float(raw.get("bid")),
            "ask": to_float(raw.get("ask")),
            "prev_close": to_float(raw.get("prev_close")),
            "open": to_float(raw.get("open")),
            "high": to_float(raw.get("high")),
            "low": to_float(raw.get("low")),
            "volume": to_float(raw.get("volume")),
            "amount": to_float(raw.get("amount")),
            "timestamp": str(raw.get("timestamp", "")),
            "updated_at": str(raw.get("updated_at", "")),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        price = item.get("price")
        return (
            item.get("stock_code") is not None
            and price is not None
            and price > 0
        )

    async def store(self, items: list[dict[str, Any]]) -> int:
        if not items:
            return 0

        from redis.asyncio import from_url

        redis = from_url(self._redis_url)
        try:
            for item in items:
                key = f"quote:{item['stock_code']}"
                await redis.setex(
                    key, self.ttl_seconds, json.dumps(item, ensure_ascii=False)
                )
        finally:
            await redis.close()

        return len(items)
