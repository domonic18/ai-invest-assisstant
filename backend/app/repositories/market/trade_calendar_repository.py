"""A 股交易日历仓储：区间查询、种子批量 upsert（不回改人工行）、单日人工覆盖。"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.models.market_trade_calendar import MarketTradeCalendar


async def get_range(
    session: AsyncSession, start: date, end: date
) -> list[MarketTradeCalendar]:
    """查询 [start, end] 闭区间的日历行，按日期升序。

    Args:
        session: 数据库会话。
        start: 起始日期（含）。
        end: 结束日期（含）。

    Returns:
        日历行列表。
    """
    stmt = (
        select(MarketTradeCalendar)
        .where(
            MarketTradeCalendar.calendar_date >= start,
            MarketTradeCalendar.calendar_date <= end,
        )
        .order_by(MarketTradeCalendar.calendar_date)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_one(
    session: AsyncSession, day: date
) -> MarketTradeCalendar | None:
    """查询单日日历行，无覆盖返回 None。"""
    stmt = select(MarketTradeCalendar).where(
        MarketTradeCalendar.calendar_date == day
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_seed_rows(
    session: AsyncSession, rows: list[dict[str, object]]
) -> int:
    """批量 upsert 种子日历行；人工覆盖行（source=manual）不被回改。

    Args:
        session: 数据库会话。
        rows: 字段含 calendar_date / is_trading（source 固定 seed）。

    Returns:
        实际写入（新增或更新）的行数。
    """
    if not rows:
        return 0
    values = [
        {
            "calendar_date": row["calendar_date"],
            "is_trading": row["is_trading"],
            "source": "seed",
            "updated_at": utc_now(),
        }
        for row in rows
    ]
    stmt = insert(MarketTradeCalendar).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[MarketTradeCalendar.calendar_date],
        set_={
            "is_trading": stmt.excluded.is_trading,
            "updated_at": stmt.excluded.updated_at,
        },
        where=MarketTradeCalendar.source == "seed",
    )
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def upsert_manual_day(
    session: AsyncSession,
    day: date,
    is_trading: bool,
    remark: str | None = None,
) -> MarketTradeCalendar:
    """单日人工覆盖：存在（seed 或 manual）则改写为 manual，不存在则插入 manual 行。"""
    now: datetime = utc_now()
    stmt = (
        insert(MarketTradeCalendar)
        .values(
            calendar_date=day,
            is_trading=is_trading,
            source="manual",
            remark=remark,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[MarketTradeCalendar.calendar_date],
            set_={
                "is_trading": is_trading,
                "source": "manual",
                "remark": remark,
                "updated_at": now,
            },
        )
    )
    await session.execute(stmt)
    return (await get_one(session, day))  # type: ignore[return-value]
