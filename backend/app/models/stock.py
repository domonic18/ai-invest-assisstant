"""SQLAlchemy ORM models for stock basic information."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StockBasic(Base):
    """股票基础信息表。"""

    __tablename__ = "stock_basic"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(50), nullable=False)
    market: Mapped[str] = mapped_column(String(4), nullable=False)
    industry_l1: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry_l2: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry_l3: Mapped[str | None] = mapped_column(String(50), nullable=True)
    listing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    circulating_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    legal_person: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)
    registered_capital: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    business_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
