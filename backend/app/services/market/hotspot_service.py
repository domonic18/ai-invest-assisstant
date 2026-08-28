"""Hotspot (sector fund flow) business services."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capital_fund_flow_sector import SectorFundFlow


async def list_sectors(
    session: AsyncSession,
    sector_type: str | None = None,
    trade_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SectorFundFlow], int]:
    """分页查询板块资金流向（热点）。

    Args:
        session: 数据库会话。
        sector_type: 板块类型筛选。
        trade_date: 交易日期筛选。
        page: 页码。
        page_size: 每页数量。

    Returns:
        (板块资金流列表, 总数)。
    """
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
    total = await session.scalar(count_stmt) or 0
    return list(result.scalars().all()), total
