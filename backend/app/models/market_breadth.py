"""SQLAlchemy ORM model for the daily market breadth snapshot."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketBreadth(Base):
    """市场涨跌统计表，支撑每日复盘的涨跌家数与情绪温度。"""

    __tablename__ = "market_breadth"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    up_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    down_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flat_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_up_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_down_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    broken_limit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("trade_date"),)
