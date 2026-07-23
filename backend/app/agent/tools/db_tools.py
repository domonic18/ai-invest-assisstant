"""Internal database tools for AI Agent."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kline import KlineDaily
from app.models.stock import StockBasic


async def query_industry_companies(
    session: AsyncSession, industry: str, limit: int = 30
) -> list[dict]:
    """查询指定一级行业的上市公司。"""
    result = await session.execute(
        select(StockBasic)
        .where(StockBasic.industry_level_1 == industry)
        .limit(limit)
    )
    return [
        {
            "stock_code": item.stock_code,
            "stock_name": item.stock_name,
            "market": item.market,
            "industry_level_2": item.industry_level_2,
            "industry_level_3": item.industry_level_3,
        }
        for item in result.scalars().all()
    ]


async def query_stock_kline(
    session: AsyncSession,
    stock_code: str,
    limit: int = 30,
) -> list[dict]:
    """查询指定股票近期 K 线数据。"""
    result = await session.execute(
        select(KlineDaily)
        .where(KlineDaily.stock_code == stock_code)
        .order_by(KlineDaily.trade_date.desc())
        .limit(limit)
    )
    return [
        {
            "trade_date": item.trade_date.isoformat(),
            "open": float(item.open) if item.open is not None else None,
            "high": float(item.high) if item.high is not None else None,
            "low": float(item.low) if item.low is not None else None,
            "close": float(item.close) if item.close is not None else None,
            "volume": item.volume,
            "amount": float(item.amount) if item.amount is not None else None,
            "change_pct": float(item.change_pct) if item.change_pct is not None else None,
        }
        for item in result.scalars().all()
    ]
