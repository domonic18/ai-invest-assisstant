"""投资日历事件查询仓储。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_event import CalendarEvent


async def list_events(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    categories: list[str] | None = None,
    limit: int = 200,
) -> list[CalendarEvent]:
    """查询 [start, end) 区间内的事件，按 event_time 升序。

    Args:
        session: 数据库会话。
        start: 起始时间（aware UTC，含）。
        end: 结束时间（aware UTC，不含）。
        categories: 分类筛选（None 表示不过滤）。
        limit: 返回条数上限。

    Returns:
        日历事件列表。
    """
    stmt = select(CalendarEvent).where(
        CalendarEvent.event_time >= start,
        CalendarEvent.event_time < end,
    )
    if categories:
        stmt = stmt.where(CalendarEvent.category.in_(categories))
    stmt = stmt.order_by(CalendarEvent.event_time).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def list_upcoming(
    session: AsyncSession, now: datetime, limit: int = 10
) -> list[CalendarEvent]:
    """查询 now 起 upcoming 的前 limit 个事件，按临近度升序。"""
    stmt = (
        select(CalendarEvent)
        .where(CalendarEvent.event_time >= now)
        .order_by(CalendarEvent.event_time)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
