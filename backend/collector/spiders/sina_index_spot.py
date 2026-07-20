"""Sina index spot collector via akshare.

实时态数据不落 PG：抓取主要指数快照写入 Redis 单键 ``market:index_spot``，
/indices 接口只读该键（与 sina_quote 的实时层一致）。盘中每分钟覆盖，
TTL 24h 保证非交易时段仍能展示收盘快照。
"""

import contextlib
import io
import json
from datetime import datetime
from typing import Any

from app.core.constants import INDEX_CODES
from collector.core.base import BaseCollector
from collector.core.config import redis_url as default_redis_url
from collector.core.parsing import to_float, to_int

REDIS_KEY = "market:index_spot"


class SinaIndexSpotCollector(BaseCollector):
    """新浪财经指数实时快照采集器（写 Redis，不落库）。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._redis_url = config.get("redis_url") or default_redis_url
        self.ttl_seconds = int(config.get("ttl_seconds", 24 * 3600))

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        # akshare 内部请求异常向上传播，交由多渠道 fallback 处理
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            df = ak.stock_zh_index_spot_sina()
        if df is None or df.empty:
            return []

        codes = symbols or list(INDEX_CODES)
        raw: list[dict[str, Any]] = []
        for code in codes:
            matched = df[df["代码"] == code]
            if matched.empty:
                continue
            row = matched.iloc[0]
            raw.append(
                {
                    "code": code,
                    "name": INDEX_CODES.get(code, str(row.get("名称", ""))),
                    "price": row["最新价"],
                    "change": row["涨跌额"],
                    "change_pct": row["涨跌幅"],
                    "volume": row.get("成交量"),
                    "amount": row.get("成交额"),
                    "quote_time": row.get("时间"),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "code": str(raw["code"]),
            "name": str(raw.get("name", "")),
            "price": to_float(raw.get("price")),
            "change": to_float(raw.get("change")),
            "change_pct": to_float(raw.get("change_pct")),
            "volume": to_int(raw.get("volume")),
            "amount": to_float(raw.get("amount")),
            "quote_time": str(raw.get("quote_time") or ""),
            "updated_at": datetime.utcnow().isoformat(),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        price = item.get("price")
        return item.get("code") is not None and price is not None and price > 0

    async def store(self, items: list[dict[str, Any]]) -> int:
        if not items:
            return 0

        from redis.asyncio import from_url

        redis = from_url(self._redis_url)
        try:
            await redis.setex(
                REDIS_KEY, self.ttl_seconds, json.dumps(items, ensure_ascii=False)
            )
        finally:
            await redis.close()
        return len(items)
