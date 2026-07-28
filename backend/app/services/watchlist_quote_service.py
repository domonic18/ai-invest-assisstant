"""自选股实时行情：Redis 快照优先，缺失时回退最近 K 线收盘。"""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.models.kline import KlineDaily
from app.models.watchlist import UserWatchlist
from app.schemas.market import WatchlistQuoteItem


async def get_watchlist_quotes(
    session: AsyncSession, user_id: int
) -> list[WatchlistQuoteItem]:
    """自选股实时行情：优先 Redis 快照，缺失时回退最近 K 线收盘价。"""
    stmt = (
        select(UserWatchlist)
        .where(UserWatchlist.user_id == user_id)
        .order_by(UserWatchlist.created_at.desc())
    )
    watch_items = list((await session.execute(stmt)).scalars().all())
    if not watch_items:
        return []

    redis = get_redis()
    quotes: dict[str, dict[str, Any]] = {}
    for item in watch_items:
        raw = await redis.get(f"quote:{item.stock_code}")
        if raw:
            quotes[item.stock_code] = json.loads(raw)

    results: list[WatchlistQuoteItem] = []
    for item in watch_items:
        cached = quotes.get(item.stock_code)
        if cached:
            results.append(
                WatchlistQuoteItem(
                    code=item.stock_code,
                    name=cached.get("stock_name"),
                    price=cached.get("price"),
                    change_pct=cached.get("change_pct"),
                    amount=cached.get("amount"),
                    tags=list(item.tags or []),
                    updated_at=cached.get("updated_at"),
                )
            )
            continue

        kline = (
            await session.execute(
                select(KlineDaily)
                .where(KlineDaily.stock_code == item.stock_code)
                .order_by(KlineDaily.trade_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        results.append(
            WatchlistQuoteItem(
                code=item.stock_code,
                price=float(kline.close) if kline and kline.close is not None else None,
                change_pct=(
                    float(kline.change_pct)
                    if kline and kline.change_pct is not None
                    else None
                ),
                amount=(
                    float(kline.amount) if kline and kline.amount is not None else None
                ),
                tags=list(item.tags or []),
                updated_at=kline.trade_date.isoformat() if kline else None,
            )
        )
    return results
