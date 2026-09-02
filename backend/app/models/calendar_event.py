"""投资日历事件的 SQLAlchemy ORM 模型。"""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CalendarEvent(Base):
    """投资日历事件（FOMC/BLS 官方日程等，source_hash 幂等）。"""

    __tablename__ = "calendar_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    impact_markets: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    related_symbols: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    source_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("source_hash"),)
