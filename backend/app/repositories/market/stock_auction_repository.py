"""个股集合竞价查询仓储。"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quote_auction_stock import AuctionData


async def list_paginated(
    session: AsyncSession,
    stock_code: str,
    *,
    trade_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AuctionData], int]:
    """按代码分页查询集合竞价数据（交易日+撮合时间倒序）。"""
    stmt = select(AuctionData).where(AuctionData.stock_code == stock_code)
    count_stmt = (
        select(func.count())
        .select_from(AuctionData)
        .where(AuctionData.stock_code == stock_code)
    )
    if trade_date:
        stmt = stmt.where(AuctionData.trade_date == trade_date)
        count_stmt = count_stmt.where(AuctionData.trade_date == trade_date)
    stmt = (
        stmt.order_by(AuctionData.trade_date.desc(), AuctionData.match_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    total = (await session.scalar(count_stmt)) or 0
    return list(result.scalars().all()), total
