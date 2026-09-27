"""交易 Agent 选股与交易计划 ORM 模型（批次 7，plan §10.1；多 Agent 基座 D23）。

agent_stock_selection 是选股依据真相源（复盘「选股对错」归因输入 +
人工移出干预记录）；agent_trade_plan 是盘中条件触发执行的真相源
（批次 8 执行服务读表推进状态机）；agent_memory 是 Agent 自有迭代
经验（复盘沉淀 + 手动沉淀，反哺每日计划 prompt；方法论基座由 KB
直读注入，见 ``agent_methodology``，方案 A 分层定版）。
三表均以 agent_key 维度隔离（trading_agent.agent_key，FK 见迁移）。
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
            "agent_key",
            "trade_date",
            "stock_code",
            name="uq_agent_stock_selection_agent_date_code",
        ),
        Index("idx_agent_stock_selection_code", "stock_code", "trade_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_key: Mapped[str] = mapped_column(String(32), nullable=False)  # 归属 Agent，FK 见迁移
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
            "agent_key",
            "plan_date",
            "stock_code",
            "plan_type",
            name="uq_agent_trade_plan_agent_date_code_type",
        ),
        Index("idx_agent_trade_plan_status", "status", "plan_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_key: Mapped[str] = mapped_column(String(32), nullable=False)  # 归属 Agent，FK 见迁移
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


class AgentMemory(Base):
    """交易 Agent 自有迭代经验（不经 KB）：复盘沉淀 + 手动沉淀。

    方法论基座由 KB 直读注入（``agent_methodology``），本表只装经验层。
    status='active' 条目由每日计划生成服务注入 prompt（条数上限截断）；
    停用 = archived（不物理删除，保留归因链路）；复盘沉淀条目按
    (source_result_id, title) 幂等。
    """

    __tablename__ = "agent_memory"
    __table_args__ = (
        UniqueConstraint(
            "agent_key", "source_result_id", "title", name="uq_agent_memory_agent_source_title"
        ),
        Index("idx_agent_memory_status", "status", "mem_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_key: Mapped[str] = mapped_column(String(32), nullable=False)  # 归属 Agent，FK 见迁移
    mem_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    source_result_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
