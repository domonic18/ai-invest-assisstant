"""集合竞价服务：个股竞价分页查询 + 指数 9:25 竞价成交额趋势。"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.constants import INDEX_CODES
from app.models.quote_auction_stock import AuctionData
from app.repositories.market import index_auction_repository
from app.schemas.stock import IndexAuctionSeries, IndexAuctionTrendResponse

# 图例展示顺序：上证指数 / 科创50 / 创业板指数
_TREND_CODES: tuple[str, ...] = ("sh000001", "sh000688", "sz399006")


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


async def get_index_auction_trend(
    session: AsyncSession,
    days: int = 30,
    start_date: date | None = None,
    end_date: date | None = None,
) -> IndexAuctionTrendResponse:
    """指数集合竞价成交额趋势（单位换算为亿元）。

    指定 start_date/end_date 时按日期区间查询，否则取最近 N 个交易日。
    """
    if start_date is not None or end_date is not None:
        rows = await index_auction_repository.list_range(
            session,
            start_date or date.min,
            end_date or today_cn(),
        )
    else:
        rows = await index_auction_repository.list_recent(session, days)
    dates = sorted({row.trade_date for row in rows})
    amounts = {
        (row.trade_date, row.index_code): round(float(row.auction_amount) / 1e8, 2)
        for row in rows
    }
    series = [
        IndexAuctionSeries(
            code=code,
            name=INDEX_CODES[code],
            values=[amounts.get((day, code)) for day in dates],
        )
        for code in _TREND_CODES
    ]
    return IndexAuctionTrendResponse(dates=dates, series=series)
