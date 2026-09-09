"""CME FedWatch 官方概率快照的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class FedWatchSnapshot(Base):
    """FedWatch 快照元数据：数据时点与当前联邦基金目标区间（每日一行，CT 日期）。"""

    __tablename__ = "fed_watch_snapshot"

    as_of_date: Mapped[date] = mapped_column(Date)
    data_as_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_range_low: Mapped[int] = mapped_column(Integer, nullable=False)
    current_range_high: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("as_of_date"),)


class FedWatchProbability(Base):
    """FedWatch 条件概率分布：各 FOMC 会议后目标区间落位概率（官网口径直存，TimescaleDB 超表）。"""

    __tablename__ = "fed_watch_probability"

    as_of_date: Mapped[date] = mapped_column(Date)
    meeting_date: Mapped[date] = mapped_column(Date)
    range_low: Mapped[int] = mapped_column(Integer)
    range_high: Mapped[int] = mapped_column(Integer, nullable=False)
    probability: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (PrimaryKeyConstraint("as_of_date", "meeting_date", "range_low"),)
