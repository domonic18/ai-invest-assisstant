"""采集健康快照的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class CollectorHealthStatus(Base):
    """任务实例（task_type × source）最近一次健康检测结果。

    由 collector_health_check 定时任务 upsert；页面只读快照，
    不在请求路径实时判定。状态翻转时间（state_changed_at）用于追溯。
    """

    __tablename__ = "collector_health_status"
    __table_args__ = (
        UniqueConstraint("task_type", "source", name="uq_collector_health_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(8), nullable=False)
    domain: Mapped[str] = mapped_column(String(16), nullable=False)
    success_rate_24h: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    success_rate_7d: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    windows_without_success: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_error_cause: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reasons: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    is_high_frequency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_records_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_records_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    state_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
