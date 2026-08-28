"""个股资金流向数据的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FundFlow(Base):
    """资金流向数据表（TimescaleDB 超表）。"""

    __tablename__ = "capital_fund_flow_stock"

    stock_code: Mapped[str] = mapped_column("stock_code")
    trade_date: Mapped[date] = mapped_column("trade_date")
    main_net_inflow: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    super_large_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    large_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    medium_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    small_net: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        PrimaryKeyConstraint("stock_code", "trade_date"),
    )
