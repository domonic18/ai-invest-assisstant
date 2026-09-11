"""异动分析日表的 SQLAlchemy ORM 模型。

表结构真源是幂等 SQL 迁移（docker/database/migrations/20260911_anomaly_tables.sql）。
检测数据源自包含（趋势 + 量价）；归因字段由 anomaly-attribution skill 回填，
证据只在归因文本中，不参与异动判定（docs/arch/08-anomaly-analysis.md）。
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class SectorAnomaly(Base):
    """板块异动日表，规则检测 + top-N 归因摘要。"""

    __tablename__ = "market_anomaly_sector"
    __table_args__ = (
        UniqueConstraint(
            "trade_date", "sector_type", "sector_code", name="uq_market_anomaly_sector"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    sector_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sector_code: Mapped[str] = mapped_column(String(16), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(50), nullable=False)
    change_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    amount_ratio: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    up_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    down_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomaly_types: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    strength: Mapped[int] = mapped_column(Integer, nullable=False)
    attribution_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    attribution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class StockAnomaly(Base):
    """个股异动日表，含 MA60 趋势上下文与有效突破标记。"""

    __tablename__ = "market_anomaly_stock"
    __table_args__ = (
        UniqueConstraint("trade_date", "stock_code", name="uq_market_anomaly_stock"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(50), nullable=False)
    close: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    ma60: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    is_above_ma60: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ma60_breakout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    anomaly_types: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    strength: Mapped[int] = mapped_column(Integer, nullable=False)
    attribution_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    attribution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
