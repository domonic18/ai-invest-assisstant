"""SQLAlchemy ORM models for fund flow data."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Numeric, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FundFlow(Base):
    """资金流向数据表（TimescaleDB 超表）。"""

    __tablename__ = "fund_flow"

    stock_code: Mapped[str] = mapped_column("stock_code")
    trade_date: Mapped[date] = mapped_column("trade_date")
    main_net_inflow: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    super_large_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    large_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    medium_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    small_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    __table_args__ = (
        PrimaryKeyConstraint("stock_code", "trade_date"),
    )
