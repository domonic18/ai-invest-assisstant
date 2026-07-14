"""SQLAlchemy ORM model for IPO information."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IpoInfo(Base):
    """新股发行信息表。"""

    __tablename__ = "ipo_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    listing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subscription_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issue_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    total_issue_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    issue_pe_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    online_winning_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    lottery_result_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    winning_announcement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    online_subscription_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    online_issue_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("stock_code", "subscription_date"),)
