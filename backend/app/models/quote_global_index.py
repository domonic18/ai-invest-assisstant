"""全球指数/指标日行情的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BIGINT, Date, DateTime, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GlobalIndexDaily(Base):
    """全球指数/指标日行情（COMEX 黄金、美元指数、美债收益率等，TimescaleDB 超表）。"""

    __tablename__ = "quote_global_index_daily"

    index_code: Mapped[str] = mapped_column(String(16))
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    low: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    close: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    volume: Mapped[int | None] = mapped_column(BIGINT)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (PrimaryKeyConstraint("index_code", "trade_date"),)
