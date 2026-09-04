"""投资日历业务服务。

日历页按 Asia/Shanghai 日历日组织（用户浏览器本地时区即北京时间），
区间参数的日期边界按 CN_TZ 换算为 aware UTC 后下发仓储查询。
"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ
from app.models.calendar_event import CalendarEvent
from app.repositories.market import calendar_repository


def _cn_day_range(start: date, end: date) -> tuple[datetime, datetime]:
    """Asia/Shanghai 日历日区间 [start 00:00, end+1 00:00) → aware UTC。"""
    start_dt = datetime.combine(start, time.min, tzinfo=CN_TZ)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=CN_TZ)
    return start_dt, end_dt


async def list_events(
    session: AsyncSession,
    start: date,
    end: date | None = None,
    categories: list[str] | None = None,
    limit: int = 200,
) -> list[CalendarEvent]:
    """查询北京日历日区间内的事件。

    Args:
        session: 数据库会话。
        start: 起始日历日（含）。
        end: 结束日历日（含），缺省与 start 相同。
        categories: 分类筛选（None 表示不过滤）。
        limit: 返回条数上限。

    Returns:
        日历事件列表。
    """
    start_dt, end_dt = _cn_day_range(start, end or start)
    return await calendar_repository.list_events(
        session, start=start_dt, end=end_dt, categories=categories, limit=limit
    )


async def list_upcoming(session: AsyncSession, limit: int = 10) -> list[CalendarEvent]:
    """查询即将发生的事件（now 起按临近度升序）。"""
    return await calendar_repository.list_upcoming(
        session, now=datetime.now(timezone.utc), limit=limit
    )
