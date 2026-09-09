"""投资日历的 Pydantic schemas。"""

from datetime import datetime

from app.schemas.base import CamelModel


class CalendarEventResponse(CamelModel):
    """投资日历事件的响应 schema。"""

    id: int
    event_time: datetime
    end_time: datetime | None = None
    title: str
    category: str
    impact_markets: list[str] | None = None
    source: str | None = None
    source_url: str | None = None
    related_symbols: list[str] | None = None
