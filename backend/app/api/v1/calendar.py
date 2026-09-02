"""投资日历 API 路由。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.calendar import CalendarEventResponse
from app.services.market import calendar_service

router = APIRouter()


@router.get("/events", response_model=list[CalendarEventResponse])
async def list_calendar_events(
    session: Annotated[AsyncSession, Depends(get_db)],
    start: date = Query(..., description="起始日历日（Asia/Shanghai，含）"),
    end: date | None = Query(None, description="结束日历日（含），缺省与 start 相同"),
    categories: str | None = Query(None, description="分类筛选，逗号分隔"),
    limit: int = Query(200, ge=1, le=500),
) -> list[CalendarEventResponse]:
    """查询日历事件，按 event_time 升序。"""
    category_list = _parse_categories(categories)
    events = await calendar_service.list_events(
        session, start=start, end=end, categories=category_list, limit=limit
    )
    return [CalendarEventResponse.model_validate(e) for e in events]


@router.get("/events/upcoming", response_model=list[CalendarEventResponse])
async def list_upcoming_calendar_events(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
) -> list[CalendarEventResponse]:
    """查询即将发生的事件（临近度升序）。"""
    events = await calendar_service.list_upcoming(session, limit=limit)
    return [CalendarEventResponse.model_validate(e) for e in events]


def _parse_categories(raw: str | None) -> list[str] | None:
    """逗号分隔的分类参数 → 去空白去重列表；空值返回 None。"""
    if not raw:
        return None
    items = [c.strip() for c in raw.split(",") if c.strip()]
    if not items:
        return None
    return items
