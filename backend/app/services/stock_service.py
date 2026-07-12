"""Stock market data business services."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auction import AuctionData
from app.models.fund_flow import FundFlow
from app.models.kline import KlineDaily
from app.models.stock import StockBasic


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
