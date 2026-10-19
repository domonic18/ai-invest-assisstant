"""基于 akshare 的新浪港股实时行情采集器。

与 A 股 ``sina_quote`` 同款缓存设计：把请求的 symbols 以
``quote:{stock_code}`` 写入 Redis（短 TTL），并写长 TTL 的
``quote:eod:{stock_code}`` 收盘兜底快照。免费港股快照统一延时
15 分钟（前端已明示），读端 ``stock_service.get_stock_quote`` 纯按
code 读缓存，无需感知市场。

akshare ``stock_hk_spot`` 为新浪全量港股表（约 99 页，30s+），仅当
存在港股自选（或缺省 symbols 传入）时才拉取。
"""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.watchlist import UserWatchlist
from collector.core.async_helpers import run_in_thread
from collector.core.base import BaseCollector, get_engine
from collector.core.config import redis_url as default_redis_url
from collector.core.parsing import clean_stock_code, to_float

# 兜底快照要覆盖「周五收盘 + 周末 + 周一节假日」，4 天足够撑到下一交易日
_EOD_TTL_SECONDS = 4 * 86400


async def _fetch_watchlist_hk_codes() -> list[str]:
    """缺省采集范围：自选股中 market='hk' 的代码去重升序。"""
    session_maker = async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        rows = await session.execute(
            select(UserWatchlist.stock_code)
            .where(UserWatchlist.market == "hk")
            .distinct()
            .order_by(UserWatchlist.stock_code)
        )
        return [row[0] for row in rows.all()]


class SinaHkQuoteCollector(BaseCollector):
    """新浪财经港股实时行情采集器（延时 15 分钟）。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._redis_url = config.get("redis_url") or default_redis_url
        self.ttl_seconds = int(config.get("ttl_seconds", 300))
        self.eod_ttl_seconds = int(config.get("eod_ttl_seconds", _EOD_TTL_SECONDS))

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        requested = (
            {clean_stock_code(code) for code in symbols}
            if symbols
            else set(await _fetch_watchlist_hk_codes())
        )
        if not requested:
            return []

        # 全市场快照单请求大表（99 页），180s 上限防无超时请求挂死线程
        df = await run_in_thread(ak.stock_hk_spot, timeout=180)
        if df is None or df.empty:
            return []

        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            code = clean_stock_code(row.get("代码"))
            if code not in requested:
                continue

            raw.append(
                {
                    "stock_code": code,
                    "stock_name": row.get("中文名称"),
                    "price": row.get("最新价"),
                    "change": row.get("涨跌额"),
                    "change_pct": row.get("涨跌幅"),
                    "bid": row.get("买一"),
                    "ask": row.get("卖一"),
                    "prev_close": row.get("昨收"),
                    "open": row.get("今开"),
                    "high": row.get("最高"),
                    "low": row.get("最低"),
                    "volume": row.get("成交量"),
                    "amount": row.get("成交额"),
                    "timestamp": row.get("日期时间") or "",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "stock_name": str(raw.get("stock_name", "")),
            "price": to_float(raw.get("price")),
            "change": to_float(raw.get("change")),
            "change_pct": to_float(raw.get("change_pct")),
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
                code = item["stock_code"]
                payload = json.dumps(item, ensure_ascii=False)
                await redis.setex(f"quote:{code}", self.ttl_seconds, payload)
                await redis.setex(
                    f"quote:eod:{code}", self.eod_ttl_seconds, payload
                )
        finally:
            await redis.close()

        return len(items)
