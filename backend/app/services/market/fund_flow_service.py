"""Stock fund flow business services."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund_flow import FundFlow


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
