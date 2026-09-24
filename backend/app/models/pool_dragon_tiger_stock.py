"""龙虎榜个股的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class DragonTigerStock(Base):
    """龙虎榜上榜个股（按交易日 × 代码 × 上榜原因唯一）。"""

    __tablename__ = "pool_dragon_tiger_stock"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rank_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    net_buy_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (UniqueConstraint("trade_date", "stock_code", "rank_reason"),)
