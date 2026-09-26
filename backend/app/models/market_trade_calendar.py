"""A 股交易日历权威真相源的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class MarketTradeCalendar(Base):
    """A 股交易日历表：source=seed 新浪日历自动生成 / manual 后台人工覆盖。"""

    __tablename__ = "market_trade_calendar"
    __table_args__ = (CheckConstraint("source IN ('seed', 'manual')"),)

    calendar_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_trading: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="seed"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
