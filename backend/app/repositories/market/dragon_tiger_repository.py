"""龙虎榜查询仓储（pool_dragon_tiger_stock）。"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pool_dragon_tiger_stock import DragonTigerStock


async def list_by_stock(
    session: AsyncSession,
    stock_code: str,
    start_date: date,
    end_date: date,
) -> list[DragonTigerStock]:
    """区间内某股的上榜记录（交易日倒序）。"""
    stmt = (
        select(DragonTigerStock)
        .where(
            DragonTigerStock.stock_code == stock_code,
            DragonTigerStock.trade_date >= start_date,
            DragonTigerStock.trade_date <= end_date,
        )
        .order_by(DragonTigerStock.trade_date.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_by_date(
    session: AsyncSession, trade_date: date
) -> list[DragonTigerStock]:
    """指定交易日的全部上榜记录（净买额降序，空值置后）。"""
    stmt = (
        select(DragonTigerStock)
        .where(DragonTigerStock.trade_date == trade_date)
        .order_by(DragonTigerStock.net_buy_amount.desc().nulls_last())
    )
    return list((await session.execute(stmt)).scalars().all())
