"""SQLAlchemy ORM models for stock basic information."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
