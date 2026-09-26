"""模拟盘交易域 ORM 模型（账户 / 委托 / 成交回报 / 资金日快照 / 交易 Agent 配置）。

表结构真源是幂等 SQL 迁移（docker/database/migrations/20260924a_paper_trade_tables.sql
与 20260926b_trading_agent_config.sql）。
柜台（掘金仿真，经 paper-trade sidecar）是交易状态真相源，本地表是复盘分析与
计划执行的真相源；16:00 盘后同步任务幂等 upsert（docs/plan/paper-trading-plan.md §4/§6）。
多租户：每用户自有掘金仿真账户（token Fernet 加密），三表账户维度，agent 账户全局唯一。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class PaperTradeAccount(Base):
    """掘金仿真账户配置：每用户自有凭证（token Fernet 加密），agent 账户全局唯一。"""

    __tablename__ = "paper_trade_account"
    __table_args__ = (
        UniqueConstraint("counter_account_id", name="uq_paper_trade_account_counter"),
        Index(
            "uq_paper_trade_account_agent",
            "is_agent",
            unique=True,
            postgresql_where=text("is_agent"),
        ),
        Index("idx_paper_trade_account_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    counter_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    is_agent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PaperTradeOrder(Base):
    """模拟盘委托：账户 + 柜台 cl_ord_id 为幂等键，保留柜台原始委托兜底字段演进。"""

    __tablename__ = "paper_trade_order"
    __table_args__ = (
        UniqueConstraint(
            "paper_trade_account_id",
            "cl_ord_id",
            name="uq_paper_trade_order_account_cl_ord_id",
        ),
        Index("idx_paper_trade_order_account_date", "paper_trade_account_id", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_trade_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_source: Mapped[str] = mapped_column(String(8), nullable=False, default="manual")
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


class TradingAgentConfig(Base):
    """交易 Agent 全局配置（单例 id=1）：LLM 绑定 + 风控阈值 + 自主执行总闸。"""

    __tablename__ = "trading_agent_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="chk_trading_agent_config_singleton"),
        {
            "comment": "交易 Agent 全局配置（单例 id=1）：LLM 绑定 + 风控阈值 + 自主执行总闸"
            "（docs/plan/paper-trading-plan.md §8.5）"
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    llm_config_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # FK 见迁移（ON DELETE SET NULL）
    methodology_source_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 方法论知识源 kb_source.id；FK 见迁移（ON DELETE SET NULL），空 = 未启用
    risk_max_position_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("20")
    )
    risk_max_total_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("80")
    )
    risk_max_daily_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    auto_exec_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PaperTradeExecution(Base):
    """模拟盘成交回报：账户 + 柜台回报 ID 为幂等键，回报不可变（冲突即跳过）。"""

    __tablename__ = "paper_trade_execution"
    __table_args__ = (
        UniqueConstraint(
            "paper_trade_account_id",
            "exec_id",
            name="uq_paper_trade_execution_account_exec_id",
        ),
        Index(
            "idx_paper_trade_execution_account_date",
            "paper_trade_account_id",
            "trade_date",
        ),
        Index("idx_paper_trade_execution_cl_ord_id", "cl_ord_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_trade_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    """模拟盘资金日快照：账户 + 一日一行，净值曲线与当日盈亏（nav 差 + 出入金修正）的唯一来源。"""

    __tablename__ = "paper_trade_cash_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "paper_trade_account_id",
            "trade_date",
            name="uq_paper_trade_cash_snapshot_account_date",
        ),
        Index(
            "idx_paper_trade_cash_snapshot_account_date",
            "paper_trade_account_id",
            "trade_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_trade_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
