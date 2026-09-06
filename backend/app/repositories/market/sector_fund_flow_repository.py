"""板块资金流向查询仓储。"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capital_fund_flow_sector import SectorFundFlow


async def list_paginated(
    session: AsyncSession,
    *,
    sector_type: str | None = None,
    trade_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SectorFundFlow], int]:
    """分页查询板块资金流（主力净流入降序，空值靠后）。"""
    stmt = select(SectorFundFlow)
    count_stmt = select(func.count()).select_from(SectorFundFlow)
    if sector_type:
        stmt = stmt.where(SectorFundFlow.sector_type == sector_type)
        count_stmt = count_stmt.where(SectorFundFlow.sector_type == sector_type)
    if trade_date:
        stmt = stmt.where(SectorFundFlow.trade_date == trade_date)
        count_stmt = count_stmt.where(SectorFundFlow.trade_date == trade_date)
    stmt = (
        stmt.order_by(SectorFundFlow.main_net_inflow.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    total = (await session.scalar(count_stmt)) or 0
    return list(result.scalars().all()), total


async def list_by_type_and_date(
    session: AsyncSession, sector_type: str, trade_date: date
) -> list[SectorFundFlow]:
    """查询指定类型与交易日的全部板块资金流。"""
    stmt = select(SectorFundFlow).where(
        SectorFundFlow.sector_type == sector_type,
        SectorFundFlow.trade_date == trade_date,
    )
    return list((await session.execute(stmt)).scalars().all())


async def latest_trade_date(session: AsyncSession) -> date | None:
    """最新一个有板块资金流数据的交易日。"""
    return await session.scalar(select(func.max(SectorFundFlow.trade_date)))


async def list_by_date_and_names(
    session: AsyncSession, trade_date: date, names: list[str]
) -> list[SectorFundFlow]:
    """查询指定交易日与板块名集合的资金流（个股所属板块资金流补充）。"""
    if not names:
        return []
    stmt = select(SectorFundFlow).where(
        SectorFundFlow.trade_date == trade_date,
        SectorFundFlow.sector_name.in_(names),
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_recent(
    session: AsyncSession, sector_type: str, days: int
) -> list[SectorFundFlow]:
    """最近 N 个有数据的交易日内指定类型板块的资金流向记录。

    按 (trade_date, main_net_inflow 降序) 排序，同日流入多的板块在前。
    """
    date_subq = (
        select(SectorFundFlow.trade_date)
        .where(SectorFundFlow.sector_type == sector_type)
        .distinct()
        .order_by(SectorFundFlow.trade_date.desc())
        .limit(days)
        .scalar_subquery()
    )
    stmt = (
        select(SectorFundFlow)
        .where(
            SectorFundFlow.sector_type == sector_type,
            SectorFundFlow.trade_date.in_(date_subq),
        )
        .order_by(
            SectorFundFlow.trade_date,
            SectorFundFlow.main_net_inflow.desc().nullslast(),
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_latest_day(
    session: AsyncSession, sector_type: str = "industry", limit: int = 8
) -> list[SectorFundFlow]:
    """最新一个有数据交易日的板块排行，主力净流入降序取前 N。"""
    latest_date = (
        select(SectorFundFlow.trade_date)
        .where(SectorFundFlow.sector_type == sector_type)
        .order_by(SectorFundFlow.trade_date.desc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        select(SectorFundFlow)
        .where(
            SectorFundFlow.sector_type == sector_type,
            SectorFundFlow.trade_date == latest_date,
        )
        .order_by(SectorFundFlow.main_net_inflow.desc().nullslast())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
