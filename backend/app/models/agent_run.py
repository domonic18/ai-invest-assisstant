"""交易 Agent 执行会话 ORM 模型（会话管理 D35）。

agent_run 是自动化任务（每日计划/分层复盘）执行会话的真相源：管理员经
「会话管理」看每次生成的触发方式、状态与结果摘要；agent_run_step 是
执行步骤明细（输入组装/KB 检索/LLM 全文/校验/落库）。观测写入走
recorder 独立 session（业务事务回滚不连带丢步骤），Agent 删除时级联
清理历史。
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class AgentRun(Base):
    """交易 Agent 自动化任务执行会话头。"""

    __tablename__ = "agent_run"
    __table_args__ = (
        Index("idx_agent_run_key_time", "agent_key", "started_at"),
        Index(
            "idx_agent_run_status_running",
            "status",
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_key: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("trading_agent.agent_key", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    trigger_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="scheduled"
    )
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    collector_log_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class AgentRunStep(Base):
    """交易 Agent 会话执行步骤明细（payload 为截断后的完整输入输出）。"""

    __tablename__ = "agent_run_step"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_agent_run_step_seq"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_run.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
