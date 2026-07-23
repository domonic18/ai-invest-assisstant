"""SQLAlchemy ORM model for the daily limit-up pool."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LimitUpPool(Base):
    """涨停股池表，支撑每日复盘的涨停板与连板天梯。"""

    __tablename__ = "pool_limit_up_stock"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    latest_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    sealed_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    first_seal_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_seal_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    broken_limit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consecutive_boards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("trade_date", "stock_code"),)
