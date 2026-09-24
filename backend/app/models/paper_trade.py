"""模拟盘交易域 ORM 模型（委托 / 成交回报 / 资金日快照）。

表结构真源是幂等 SQL 迁移（docker/database/migrations/20260924a_paper_trade_tables.sql）。
柜台（掘金仿真，经 paper-trade sidecar）是交易状态真相源，本地表是复盘分析与
计划执行的真相源；16:00 盘后同步任务幂等 upsert（docs/plan/paper-trading-plan.md §4）。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class PaperTradeOrder(Base):
    """模拟盘委托：柜台 cl_ord_id 为幂等键，保留柜台原始委托兜底字段演进。"""

    __tablename__ = "paper_trade_order"
    __table_args__ = (
        UniqueConstraint("cl_ord_id", name="uq_paper_trade_order_cl_ord_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cl_ord_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    side: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    order_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    position_effect: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=0
    )
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ord_rej_reason: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    ord_rej_reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    counter_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    counter_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PaperTradeExecution(Base):
    """模拟盘成交回报：柜台回报 ID 为幂等键，回报不可变（冲突即跳过）。"""

    __tablename__ = "paper_trade_execution"
    __table_args__ = (
        UniqueConstraint("exec_id", name="uq_paper_trade_execution_exec_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exec_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cl_ord_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    exec_type: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    commission: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    counter_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PaperTradeCashSnapshot(Base):
    """模拟盘资金日快照：一日一行，净值曲线与当日盈亏（nav 差 + 出入金修正）的唯一来源。"""

    __tablename__ = "paper_trade_cash_snapshot"
    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_paper_trade_cash_snapshot_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    available: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    cum_inout: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    last_inout: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
