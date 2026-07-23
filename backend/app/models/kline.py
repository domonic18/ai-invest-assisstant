"""SQLAlchemy ORM models for K-line data."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BIGINT, DateTime, Numeric, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KlineDaily(Base):
    """日 K 线数据表（TimescaleDB 超表）。"""

    __tablename__ = "quote_kline_stock_daily"

    stock_code: Mapped[str] = mapped_column("stock_code")
    trade_date: Mapped[date] = mapped_column("trade_date")
    open: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    volume: Mapped[int | None] = mapped_column(BIGINT)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    amplitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        PrimaryKeyConstraint("stock_code", "trade_date"),
    )


class KlineMinute(Base):
    """分钟 K 线数据表（TimescaleDB 超表），目前承载指数 1 分钟线。"""

    __tablename__ = "quote_kline_stock_minute"

    stock_code: Mapped[str] = mapped_column("stock_code")
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    volume: Mapped[int | None] = mapped_column(BIGINT)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        PrimaryKeyConstraint("stock_code", "trade_time"),
    )
