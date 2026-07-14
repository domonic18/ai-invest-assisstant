"""SQLAlchemy ORM model for cash flow statement."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CashFlowStatement(Base):
    """现金流量表。"""

    __tablename__ = "cash_flow_statement"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_type: Mapped[str] = mapped_column(String(10), nullable=False)
    cf_operations: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    cf_investing: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    cf_financing: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    net_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
