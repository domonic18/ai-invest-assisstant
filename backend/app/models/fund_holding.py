"""SQLAlchemy ORM model for fund holdings."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BIGINT, Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FundHolding(Base):
    """个股基金持仓表。"""

    __tablename__ = "fund_holding"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    holding_fund_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_holding_quantity: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    holding_market_value: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    holding_change: Mapped[str | None] = mapped_column(String(20), nullable=True)
    holding_change_quantity: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    holding_change_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("stock_code", "report_date"),)
