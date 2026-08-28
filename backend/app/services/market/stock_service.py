"""个股基础信息与行情业务服务。"""

import json
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.models.capital_fund_flow_sector import SectorFundFlow
from app.models.stock import StockBasic
from app.repositories.market.kline_repository import fetch_daily_bars
from app.repositories.market.stock_concept_repository import StockConceptRepository


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

    # 用最新板块资金流统计做补充
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
