"""SQLAlchemy ORM model for balance sheet."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BalanceSheet(Base):
    """资产负债表。"""

    __tablename__ = "balance_sheet"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_type: Mapped[str] = mapped_column(String(10), nullable=False)
    total_assets: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    current_assets: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    cash_equivalents: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    accounts_receivable: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    inventory: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    fixed_assets: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    intangible_assets: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    goodwill: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    total_liabilities: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    current_liabilities: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    long_term_debt: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    paid_in_capital: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    retained_earnings: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
