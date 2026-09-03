"""自选股实时行情：Redis 快照优先，缺失时回退最近 K 线收盘。"""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.models.stock import StockBasic
from app.models.watchlist import UserWatchlist
from app.repositories.market.kline_repository import (
    fetch_daily_bars,
    fetch_minute_bars_multi,
)
from app.schemas.market import WatchlistQuoteItem
from app.services.market import trade_calendar_service
from app.services.market.intraday_utils import downsample


async def _load_stock_names(
    session: AsyncSession, codes: list[str]
) -> dict[str, str]:
    """stock_basic 批量取股票名称（Redis 快照缺失时的兜底）。"""
    rows = await session.execute(
        select(StockBasic.stock_code, StockBasic.stock_name).where(
            StockBasic.stock_code.in_(codes)
        )
    )
    return {code: name for code, name in rows.all()}


async def _load_minute_trend(
    session: AsyncSession, codes: list[str]
) -> dict[str, list[float]]:
    """最近交易日分钟收盘价降采样（≤60 点），无数据返回空数组。"""
    resolved = await trade_calendar_service.resolve_latest_trade_date(session)
    bars = await fetch_minute_bars_multi(session, codes, resolved)
    closes_by_code: dict[str, list[float]] = {}
    for bar in bars:
        if bar.close is None:
            continue
        closes_by_code.setdefault(bar.stock_code, []).append(float(bar.close))
    return {code: downsample(closes) for code, closes in closes_by_code.items() if closes}


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

    codes = [item.stock_code for item in watch_items]
    redis = get_redis()
    quotes: dict[str, dict[str, Any]] = {}
    for item in watch_items:
        raw = await redis.get(f"quote:{item.stock_code}")
        if raw:
            quotes[item.stock_code] = json.loads(raw)

    names = await _load_stock_names(session, codes)
    trends = await _load_minute_trend(session, codes)

    results: list[WatchlistQuoteItem] = []
    for item in watch_items:
        trend = trends.get(item.stock_code, [])
        cached = quotes.get(item.stock_code)
        if cached:
            results.append(
                WatchlistQuoteItem(
                    code=item.stock_code,
                    name=cached.get("stock_name") or names.get(item.stock_code),
                    price=cached.get("price"),
                    change_pct=cached.get("change_pct"),
                    amount=cached.get("amount"),
                    tags=list(item.tags or []),
                    updated_at=cached.get("updated_at"),
                    trend=trend,
                )
            )
            continue

        daily = [
            bar
            for bar in await fetch_daily_bars(session, item.stock_code, limit=2)
            if bar.close is not None
        ]
        latest = daily[0] if daily else None
        prev = daily[1] if len(daily) > 1 else None
        # 日 K 渠道多缺 change_pct 字段，缺省时按前收盘推算（与 get_stock_quote 同口径）
        price: float | None = None
        change_pct: float | None = None
        amount: float | None = None
        if latest is not None and latest.close is not None:
            price = float(latest.close)
            if latest.change_pct is not None:
                change_pct = float(latest.change_pct)
            elif prev is not None and prev.close:
                change_pct = (price - float(prev.close)) / float(prev.close) * 100
            if latest.amount is not None:
                amount = float(latest.amount)
        results.append(
            WatchlistQuoteItem(
                code=item.stock_code,
                name=names.get(item.stock_code),
                price=price,
                change_pct=change_pct,
                amount=amount,
                tags=list(item.tags or []),
                updated_at=latest.trade_date.isoformat() if latest is not None else None,
                trend=trend,
            )
        )
    return results
