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


async def list_all_by_date(
    session: AsyncSession, trade_date: date
) -> list[SectorQuoteDaily]:
    """指定快照日的全部板块行（行业 + 概念），异动检测扫描用。"""
    stmt = select(SectorQuoteDaily).where(SectorQuoteDaily.trade_date == trade_date)
    return list((await session.execute(stmt)).scalars().all())


async def recent_trade_dates(
    session: AsyncSession, before: date, limit: int = 5
) -> list[date]:
    """目标日之前最近 limit 个快照日（降序），量能基线窗口用。"""
    stmt = (
        select(SectorQuoteDaily.trade_date)
        .where(SectorQuoteDaily.trade_date < before)
        .distinct()
        .order_by(SectorQuoteDaily.trade_date.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def avg_amount_by_sector(
    session: AsyncSession, trade_dates: list[date]
) -> dict[tuple[str, str], tuple[float, int]]:
    """基线窗口内各板块平均成交额与有效天数，键为 (sector_type, sector_code)。"""
    if not trade_dates:
        return {}
    stmt = (
        select(
            SectorQuoteDaily.sector_type,
            SectorQuoteDaily.sector_code,
            func.avg(SectorQuoteDaily.amount),
            func.count(SectorQuoteDaily.amount),
        )
        .where(SectorQuoteDaily.trade_date.in_(trade_dates))
        .group_by(SectorQuoteDaily.sector_type, SectorQuoteDaily.sector_code)
    )
    rows = (await session.execute(stmt)).all()
    return {
        (row[0], row[1]): (float(row[2]), int(row[3]))
        for row in rows
        if row[2] is not None
    }


async def latest_sector_quote(
    session: AsyncSession, sector_type: str, sector_code: str
) -> SectorQuoteDaily | None:
    """单板块最新一条收盘快照（板块详情页快照卡）。"""
    stmt = (
        select(SectorQuoteDaily)
        .where(
            SectorQuoteDaily.sector_type == sector_type,
            SectorQuoteDaily.sector_code == sector_code,
        )
        .order_by(SectorQuoteDaily.trade_date.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()
