"""SQLAlchemy ORM models for K-line data."""

from datetime import date
from decimal import Decimal

from sqlalchemy import BIGINT, Numeric, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KlineDaily(Base):
    """日 K 线数据表（TimescaleDB 超表）。"""

    __tablename__ = "kline_daily"

    stock_code: Mapped[str] = mapped_column("stock_code")
    trade_date: Mapped[date] = mapped_column("trade_date")
    open: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    volume: Mapped[int | None] = mapped_column(BIGINT)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    amplitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    __table_args__ = (
        PrimaryKeyConstraint("stock_code", "trade_date"),
    )
