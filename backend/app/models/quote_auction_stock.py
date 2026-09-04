"""个股集合竞价数据的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import ARRAY, BIGINT, DATE, DateTime, Numeric, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuctionData(Base):
    """集合竞价数据表。"""

    __tablename__ = "quote_auction_stock"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[date] = mapped_column(DATE, nullable=False)
    match_time: Mapped[time] = mapped_column(Time, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    volume: Mapped[int | None] = mapped_column(BIGINT)
    bid_prices: Mapped[list[Decimal | None] | None] = mapped_column(ARRAY(Numeric(12, 3)))
    bid_volumes: Mapped[list[int | None] | None] = mapped_column(ARRAY(BIGINT))
    ask_prices: Mapped[list[Decimal | None] | None] = mapped_column(ARRAY(Numeric(12, 3)))
    ask_volumes: Mapped[list[int | None] | None] = mapped_column(ARRAY(BIGINT))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", "match_time"),
    )
