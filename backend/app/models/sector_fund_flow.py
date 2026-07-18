"""SQLAlchemy ORM model for sector fund flow."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SectorFundFlow(Base):
    """板块资金流向表，用于热点追踪。"""

    __tablename__ = "sector_fund_flow"

    sector_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    main_net_inflow: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    super_large_net: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    large_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    medium_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    small_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    top_stock_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    top_stock_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("sector_code", "sector_type", "trade_date"),
    )
