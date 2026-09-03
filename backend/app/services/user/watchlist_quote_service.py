"""自选股实时行情：Redis 快照优先，缺失时回退最近 K 线收盘。"""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.models.kline import KlineDaily
from app.models.stock import StockBasic
from app.models.watchlist import UserWatchlist
from app.repositories.market.kline_repository import fetch_minute_bars_multi
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
                name=names.get(item.stock_code),
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
                trend=trend,
            )
        )
    return results
