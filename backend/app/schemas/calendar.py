"""投资日历的 Pydantic schemas。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CalendarEventResponse(BaseModel):
    """投资日历事件的响应 schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_time: datetime
    end_time: datetime | None = None
    title: str
    category: str
    impact_markets: list[str] | None = None
    source: str | None = None
    source_url: str | None = None
    related_symbols: list[str] | None = None
