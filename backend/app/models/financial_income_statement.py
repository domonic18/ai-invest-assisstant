"""利润表的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IncomeStatement(Base):
    """利润表。"""

    __tablename__ = "financial_income_statement"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_type: Mapped[str] = mapped_column(String(10), nullable=False)
    total_revenue: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    operating_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    selling_expense: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    admin_expense: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    research_development_expense: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    finance_expense: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    operating_profit: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    net_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    net_profit_deducted: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
