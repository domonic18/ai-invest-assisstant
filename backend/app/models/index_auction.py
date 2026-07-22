"""SQLAlchemy ORM model for index call-auction turnover."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IndexAuction(Base):
    """指数集合竞价成交额表，9:25 竞价撮合成交额（单位：元）。"""

    __tablename__ = "index_auction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    index_code: Mapped[str] = mapped_column(String(10), nullable=False)
    auction_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("trade_date", "index_code"),)
