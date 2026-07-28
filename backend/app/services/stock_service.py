"""Stock market data business services."""

import json
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.models.auction import AuctionData
from app.models.capital_fund_flow_sector import SectorFundFlow
from app.models.fund_flow import FundFlow
from app.models.kline import KlineDaily
from app.models.stock import StockBasic
from app.repositories.kline_repository import (
    PERIOD_BUCKET,
    fetch_aggregated_bars,
    fetch_daily_bars,
    fetch_minute_bars,
    latest_minute_day,
    prev_minute_close,
)
from app.repositories.stock_concept_repository import StockConceptRepository

_CN_TZ = ZoneInfo("Asia/Shanghai")


def _to_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _to_int(value: Any) -> int | None:
    return int(value) if value is not None else None


async def search_stocks(
    session: AsyncSession, query: str, limit: int = 20
) -> list[StockBasic]:
    """根据股票代码或名称模糊搜索。"""
    pattern = f"%{query}%"
    result = await session.execute(
        select(StockBasic)
        .where(
            (StockBasic.stock_code.ilike(pattern))
            | (StockBasic.stock_name.ilike(pattern))
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_stock_by_code(
    session: AsyncSession, stock_code: str, market: str | None = None
) -> StockBasic | None:
    """通过股票代码查询基础信息。"""
    stmt = select(StockBasic).where(StockBasic.stock_code == stock_code)
    if market:
        stmt = stmt.where(StockBasic.market == market)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_kline_by_code(
    session: AsyncSession,
    stock_code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KlineDaily], int]:
    """分页查询日 K 线数据。"""
    stmt = select(KlineDaily).where(KlineDaily.stock_code == stock_code)
    count_stmt = select(func.count()).select_from(KlineDaily).where(KlineDaily.stock_code == stock_code)

    if start_date:
        stmt = stmt.where(KlineDaily.trade_date >= start_date)
        count_stmt = count_stmt.where(KlineDaily.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(KlineDaily.trade_date <= end_date)
        count_stmt = count_stmt.where(KlineDaily.trade_date <= end_date)

    stmt = stmt.order_by(KlineDaily.trade_date.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(stmt)
    total = await session.scalar(count_stmt) or 0
    return list(result.scalars().all()), total


async def get_auction_by_code(
    session: AsyncSession,
    stock_code: str,
    trade_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AuctionData], int]:
    """分页查询集合竞价数据。"""
    stmt = select(AuctionData).where(AuctionData.stock_code == stock_code)
    count_stmt = select(func.count()).select_from(AuctionData).where(AuctionData.stock_code == stock_code)

    if trade_date:
        stmt = stmt.where(AuctionData.trade_date == trade_date)
        count_stmt = count_stmt.where(AuctionData.trade_date == trade_date)

    stmt = stmt.order_by(AuctionData.trade_date.desc(), AuctionData.match_time.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(stmt)
    total = await session.scalar(count_stmt) or 0
    return list(result.scalars().all()), total


async def get_fund_flow(
    session: AsyncSession,
    stock_code: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[FundFlow], int]:
    """分页查询资金流向数据。"""
    stmt = select(FundFlow)
    count_stmt = select(func.count()).select_from(FundFlow)

    if stock_code:
        stmt = stmt.where(FundFlow.stock_code == stock_code)
        count_stmt = count_stmt.where(FundFlow.stock_code == stock_code)
    if start_date:
        stmt = stmt.where(FundFlow.trade_date >= start_date)
        count_stmt = count_stmt.where(FundFlow.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(FundFlow.trade_date <= end_date)
        count_stmt = count_stmt.where(FundFlow.trade_date <= end_date)

    stmt = stmt.order_by(FundFlow.trade_date.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(stmt)
    total = await session.scalar(count_stmt) or 0
    return list(result.scalars().all()), total


async def get_stock_quote(session: AsyncSession, stock_code: str) -> dict[str, Any] | None:
    """获取个股实时行情快照，Redis 缺失时回退到最新日 K。"""
    stock = await get_stock_by_code(session, stock_code)
    if stock is None:
        return None

    name = stock.stock_name or stock_code
    price: float | None = None
    prev_close: float | None = None
    open_: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    amount: float | None = None
    updated_at: str | None = None

    raw = await get_redis().get(f"quote:{stock_code}")
    if raw:
        cached = json.loads(raw)
        price = _to_float(cached.get("price"))
        prev_close = _to_float(cached.get("prev_close"))
        open_ = _to_float(cached.get("open"))
        high = _to_float(cached.get("high"))
        low = _to_float(cached.get("low"))
        volume = _to_int(cached.get("volume"))
        amount = _to_float(cached.get("amount"))
        updated_at = cached.get("updated_at")

    if price is None:
        # Redis 未命中，回退到最近两根日 K
        daily = await fetch_daily_bars(session, stock_code, limit=2)
        daily = [bar for bar in daily if bar.close is not None]
        if not daily:
            return None
        latest = daily[0]
        price = _to_float(latest.close)
        prev = daily[1] if len(daily) > 1 else None
        prev_close = _to_float(prev.close) if prev else price
        open_ = _to_float(latest.open)
        high = _to_float(latest.high)
        low = _to_float(latest.low)
        volume = _to_int(latest.volume)
        amount = _to_float(latest.amount)
        updated_at = latest.trade_date.isoformat()

    change = (price - prev_close) if price is not None and prev_close is not None else None
    change_pct = (change / prev_close * 100) if change is not None and prev_close else None
    market_cap = (
        price * stock.total_shares
        if price is not None and stock.total_shares is not None
        else None
    )
    circulating_market_cap = (
        price * stock.circulating_shares
        if price is not None and stock.circulating_shares is not None
        else None
    )

    return {
        "code": stock_code,
        "name": name,
        "price": price,
        "prev_close": prev_close,
        "change": round(change, 4) if change is not None else None,
        "change_pct": round(change_pct, 4) if change_pct is not None else None,
        "open": open_,
        "high": high,
        "low": low,
        "volume": volume,
        "amount": amount,
        "market_cap": market_cap,
        "circulating_market_cap": circulating_market_cap,
        "updated_at": updated_at,
    }


async def get_stock_kline(
    session: AsyncSession,
    stock_code: str,
    period: str = "daily",
    limit: int = 250,
) -> dict[str, Any]:
    """获取个股多周期 K 线（升序返回）。"""
    stock = await get_stock_by_code(session, stock_code)
    if stock is None:
        raise ValueError(f"股票 {stock_code} 不存在")

    if period == "daily":
        rows = await fetch_daily_bars(session, stock_code, limit=limit)
        bars = [
            {
                "date": row.trade_date,
                "open": _to_float(row.open),
                "high": _to_float(row.high),
                "low": _to_float(row.low),
                "close": _to_float(row.close),
                "volume": _to_int(row.volume),
                "amount": _to_float(row.amount),
            }
            for row in reversed(rows)
        ]
    else:
        bucket = PERIOD_BUCKET.get(period)
        if bucket is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        agg_rows = await fetch_aggregated_bars(session, stock_code, bucket, limit=limit)
        bars = [
            {
                "date": row["bucket_date"],
                "open": _to_float(row["open"]),
                "high": _to_float(row["high"]),
                "low": _to_float(row["low"]),
                "close": _to_float(row["close"]),
                "volume": _to_int(row["volume"]),
                "amount": _to_float(row["amount"]),
            }
            for row in reversed(agg_rows)
        ]

    return {
        "code": stock_code,
        "name": stock.stock_name or stock_code,
        "period": period,
        "bars": bars,
    }


async def get_stock_intraday(
    session: AsyncSession,
    stock_code: str,
    trade_date: date | None = None,
) -> dict[str, Any]:
    """获取个股分时数据（价格 + 成交量）。"""
    stock = await get_stock_by_code(session, stock_code)
    if stock is None:
        raise ValueError(f"股票 {stock_code} 不存在")

    target = trade_date or await latest_minute_day(session, stock_code)
    if target is None:
        return {
            "code": stock_code,
            "name": stock.stock_name or stock_code,
            "trade_date": date.today(),
            "prev_close": 0.0,
            "points": [],
        }

    bars = await fetch_minute_bars(session, stock_code, target)
    prev_close = await prev_minute_close(session, stock_code, target)
    if prev_close is None:
        daily = await fetch_daily_bars(session, stock_code, end_date=target, limit=2)
        earlier = [bar for bar in daily if bar.trade_date < target and bar.close]
        prev_close = _to_float(earlier[0].close) if earlier else None
    if prev_close is None:
        prev_close = _to_float(bars[0].close) if bars and bars[0].close else 0.0

    points = [
        {
            "time": bar.trade_time.astimezone(_CN_TZ).strftime("%H:%M"),
            "price": _to_float(bar.close) or 0.0,
            "volume": _to_int(bar.volume) or 0,
            "amount": _to_float(bar.amount) or 0.0,
        }
        for bar in bars
    ]
    return {
        "code": stock_code,
        "name": stock.stock_name or stock_code,
        "trade_date": target,
        "prev_close": prev_close,
        "points": points,
    }


async def get_stock_sectors(session: AsyncSession, stock_code: str) -> dict[str, Any] | None:
    """获取个股所属行业与概念，附带最新板块资金流。"""
    stock = await get_stock_by_code(session, stock_code)
    if stock is None:
        return None

    sectors: list[dict[str, Any]] = []
    for level, label in (
        (stock.industry_level_1, "industry"),
        (stock.industry_level_2, "industry"),
        (stock.industry_level_3, "industry"),
    ):
        if level:
            sectors.append({"name": level, "type": label})

    concept_repo = StockConceptRepository(session)
    concepts = await concept_repo.get_concepts_by_stock(stock_code)
    for concept in concepts:
        sectors.append({"name": concept.concept_name, "type": "concept"})

    #  enrichment with latest sector fund flow stats
    latest_date = (
        await session.scalar(
            select(func.max(SectorFundFlow.trade_date))
        )
    ) or date.today()
    flow_rows = list(
        (
            await session.execute(
                select(SectorFundFlow).where(
                    SectorFundFlow.trade_date == latest_date,
                    SectorFundFlow.sector_name.in_([s["name"] for s in sectors]),
                )
            )
        )
        .scalars()
        .all()
    )
    flow_by_name = {row.sector_name: row for row in flow_rows}

    enriched = []
    for item in sectors:
        row = flow_by_name.get(item["name"])
        enriched.append(
            {
                "name": item["name"],
                "type": item["type"],
                "change_pct": _to_float(row.change_pct) if row else None,
                "main_net_inflow": _to_float(row.main_net_inflow) if row else None,
            }
        )

    return {
        "code": stock_code,
        "name": stock.stock_name or stock_code,
        "sectors": enriched,
    }
