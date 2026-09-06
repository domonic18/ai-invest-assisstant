"""涨停池查询仓储（pool_limit_up_stock）。"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pool_limit_up_stock import LimitUpPool


async def list_by_date(session: AsyncSession, trade_date: date) -> list[LimitUpPool]:
    """指定交易日涨停池（连板数降序、封单金额降序，空值靠后）。"""
    stmt = (
        select(LimitUpPool)
        .where(LimitUpPool.trade_date == trade_date)
        .order_by(
            LimitUpPool.consecutive_boards.desc().nullslast(),
            LimitUpPool.sealed_amount.desc().nullslast(),
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_codes_by_date(
    session: AsyncSession, trade_date: date
) -> list[str]:
    """指定交易日涨停股代码列表。"""
    stmt = select(LimitUpPool.stock_code).where(LimitUpPool.trade_date == trade_date)
    return list((await session.execute(stmt)).scalars().all())


async def count_by_date(session: AsyncSession, trade_date: date) -> int:
    """指定交易日涨停家数（官方池口径，不含 ST 股）。"""
    return await session.scalar(
        select(func.count())
        .select_from(LimitUpPool)
        .where(LimitUpPool.trade_date == trade_date)
    ) or 0


async def count_continuous_by_date(
    session: AsyncSession, trade_date: date
) -> int:
    """指定交易日连板（≥2 板）家数。"""
    return await session.scalar(
        select(func.count())
        .select_from(LimitUpPool)
        .where(
            LimitUpPool.trade_date == trade_date,
            LimitUpPool.consecutive_boards >= 2,
        )
    ) or 0
