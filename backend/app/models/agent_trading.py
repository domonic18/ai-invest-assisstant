"""交易 Agent 选股与交易计划 ORM 模型（批次 7，plan §10.1）。

agent_stock_selection 是选股依据真相源（复盘「选股对错」归因输入 +
人工移出干预记录）；agent_trade_plan 是盘中条件触发执行的真相源
（批次 8 执行服务读表推进状态机）。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class AgentStockSelection(Base):
    """交易 Agent 每日选股清单（选入/移出与依据的真相源）。"""

    __tablename__ = "agent_stock_selection"
    __table_args__ = (
        UniqueConstraint(
            "trade_date", "stock_code", name="uq_agent_stock_selection_date_code"
        ),
        Index("idx_agent_stock_selection_code", "stock_code", "trade_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_result_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    removed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AgentTradePlan(Base):
    """交易 Agent 每日交易计划（盘中条件触发执行的真相源）。

    状态机：active → triggered（已触发下单）→ executed / expired（当日未触发）
    / cancelled（人工取消）。
    """

    __tablename__ = "agent_trade_plan"
    __table_args__ = (
        UniqueConstraint(
            "plan_date", "stock_code", "plan_type", name="uq_agent_trade_plan_date_code_type"
        ),
        Index("idx_agent_trade_plan_status", "status", "plan_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(8), nullable=False)
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    buy_zone_low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    buy_zone_high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    position_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    selection_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    basis: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_cl_ord_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
