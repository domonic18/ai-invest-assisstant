"""Stock auction business services."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auction import AuctionData


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
