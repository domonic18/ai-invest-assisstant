"""指数集合竞价成交额查询仓储。"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quote_auction_index import IndexAuction


async def list_recent(session: AsyncSession, days: int) -> list[IndexAuction]:
    """最近 N 个有数据的交易日的全部指数竞价记录，按 (trade_date, index_code) 升序。"""
    date_subq = (
        select(IndexAuction.trade_date)
        .distinct()
        .order_by(IndexAuction.trade_date.desc())
        .limit(days)
        .scalar_subquery()
    )
    stmt = (
        select(IndexAuction)
        .where(IndexAuction.trade_date.in_(date_subq))
        .order_by(IndexAuction.trade_date, IndexAuction.index_code)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_range(
    session: AsyncSession, start_date: date, end_date: date
) -> list[IndexAuction]:
    """指定日期区间内的全部指数竞价记录，按 (trade_date, index_code) 升序。"""
    stmt = (
        select(IndexAuction)
        .where(
            IndexAuction.trade_date >= start_date,
            IndexAuction.trade_date <= end_date,
        )
        .order_by(IndexAuction.trade_date, IndexAuction.index_code)
    )
    return list((await session.execute(stmt)).scalars().all())
