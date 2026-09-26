"""模拟盘交易域 ORM 模型（账户 / 委托 / 成交回报 / 资金日快照 / 交易 Agent 注册表）。

表结构真源是幂等 SQL 迁移（docker/database/migrations/20260924a_paper_trade_tables.sql
与 20260926g_trading_agent_registry.sql）。
柜台（掘金仿真，经 paper-trade sidecar）是交易状态真相源，本地表是复盘分析与
计划执行的真相源；16:00 盘后同步任务幂等 upsert（docs/plan/paper-trading-plan.md §4/§6）。
多租户：每用户自有掘金仿真账户（token Fernet 加密），三表账户维度；
agent 账户经 agent_key 与 trading_agent 注册表一一绑定（docs/plan/agent-hub-plan.md D22）。
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
    """掘金仿真账户配置：每用户自有凭证（token Fernet 加密），agent 账户按 agent_key 唯一。"""

    __tablename__ = "paper_trade_account"
    __table_args__ = (
        UniqueConstraint("counter_account_id", name="uq_paper_trade_account_counter"),
        Index(
            "uq_paper_trade_account_agent_key",
            "agent_key",
            unique=True,
            postgresql_where=text("agent_key IS NOT NULL"),
        ),
        Index("idx_paper_trade_account_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    counter_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_key: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # 归属交易 Agent；NULL = 用户账户。FK 见迁移（ON DELETE RESTRICT）
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


class TradingAgent(Base):
    """交易 Agent 注册表：身份/介绍/模型绑定/风控/总闸/频率（D21 + D28）。

    status='active' 参与执行与调度且总览可见；'planned' 种子初始态（隐藏不跑，
    启用时置 active）；'disabled' 停用（隐藏不跑）。plan/review_cadence 决定
    计划与复盘的生成频率（daily 每交易日 / weekly 周末 / monthly 月末）。
    种子-only：新 Agent 手工 SQL 注册（INSERT 本表一行即可，技能/人设模板可选），
    管理端不做 CRUD。
    """

    __tablename__ = "trading_agent"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'planned', 'disabled')", name="chk_trading_agent_status"
        ),
        CheckConstraint(
            "plan_cadence IN ('daily', 'weekly', 'monthly')",
            name="chk_trading_agent_plan_cadence",
        ),
        CheckConstraint(
            "review_cadence IN ('daily', 'weekly', 'monthly')",
            name="chk_trading_agent_review_cadence",
        ),
        {
            "comment": "交易 Agent 注册表：身份/介绍/模型绑定/风控/总闸"
            "（docs/plan/agent-hub-plan.md D21）"
        },
    )

    agent_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    tagline: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    strategy_desc: Mapped[str] = mapped_column(Text, nullable=False, default="")
    style_desc: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    llm_config_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 对话/结构化输出模型；FK 见迁移（ON DELETE SET NULL），空 = 默认 chat
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
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    plan_cadence: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")
    review_cadence: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # prompts/agents/<prompt_id>.yaml；人设身份段经注册表运行时注入（D28）
    accent_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#3b82f6")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
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
