"""板块资金流向查询仓储。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capital_fund_flow_sector import SectorFundFlow


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
