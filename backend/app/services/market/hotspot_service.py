"""热点（板块资金流向）业务服务。"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capital_fund_flow_sector import SectorFundFlow
from app.repositories.market import sector_fund_flow_repository


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
    return await sector_fund_flow_repository.list_paginated(
        session,
        sector_type=sector_type,
        trade_date=trade_date,
        page=page,
        page_size=page_size,
    )
