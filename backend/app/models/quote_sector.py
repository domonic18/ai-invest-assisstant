"""行业/概念板块收盘快照的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BIGINT, Date, DateTime, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class SectorQuoteDaily(Base):
    """板块收盘快照（东财行业/概念 clist，成交额/换手/涨跌家数/领涨股，TimescaleDB 超表）。"""

    __tablename__ = "quote_sector_daily"

    sector_type: Mapped[str] = mapped_column(String(16))
    sector_code: Mapped[str] = mapped_column(String(16))
    sector_name: Mapped[str] = mapped_column(String(50), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date)
    close: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    up_count: Mapped[int | None] = mapped_column(BIGINT)
    down_count: Mapped[int | None] = mapped_column(BIGINT)
    leader_stock_name: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (PrimaryKeyConstraint("sector_type", "sector_code", "trade_date"),)
