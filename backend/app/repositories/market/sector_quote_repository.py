"""板块收盘快照查询仓储。"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quote_sector import SectorQuoteDaily


async def latest_trade_date(
    session: AsyncSession, sector_type: str
) -> date | None:
    """该板块类型最新快照日（无数据返回 None）。"""
    stmt = select(func.max(SectorQuoteDaily.trade_date)).where(
        SectorQuoteDaily.sector_type == sector_type
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_sector_quotes(
    session: AsyncSession, sector_type: str, trade_date: date
) -> list[SectorQuoteDaily]:
    """指定快照日的板块行，按涨跌幅降序（NULL 排尾）。"""
    stmt = (
        select(SectorQuoteDaily)
        .where(
            SectorQuoteDaily.sector_type == sector_type,
            SectorQuoteDaily.trade_date == trade_date,
        )
        .order_by(SectorQuoteDaily.change_pct.desc().nulls_last())
    )
    return list((await session.execute(stmt)).scalars().all())
