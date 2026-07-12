"""SQLAlchemy ORM models for auction data."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, BIGINT, DATE, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuctionData(Base):
    """集合竞价数据表。"""

    __tablename__ = "auction_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[date] = mapped_column(DATE, nullable=False)
    match_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    volume: Mapped[int | None] = mapped_column(BIGINT)
    bid_prices: Mapped[list[Decimal | None] | None] = mapped_column(ARRAY(Numeric(12, 3)))
    bid_volumes: Mapped[list[int | None] | None] = mapped_column(ARRAY(BIGINT))
    ask_prices: Mapped[list[Decimal | None] | None] = mapped_column(ARRAY(Numeric(12, 3)))
    ask_volumes: Mapped[list[int | None] | None] = mapped_column(ARRAY(BIGINT))

    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", "match_time"),
    )
