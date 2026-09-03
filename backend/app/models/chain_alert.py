"""产业链 AI 提醒的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ALERT_TYPES = ("财报异动", "评级调整", "技术突破", "格局变化", "政策催化")


class ChainAlert(Base):
    """产业链提醒（分析任务产出的具名告警，同链同类型同日唯一）。"""

    __tablename__ = "chain_alert"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    industry: Mapped[str] = mapped_column(String(50), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_segments: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    related_stock_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(10)), nullable=True
    )
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey("industry_chain_analysis_version.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "industry", "alert_type", "signal_date", name="uq_chain_alert_industry_type_date"
        ),
        Index("idx_chain_alert_industry_signal", "industry", "signal_date"),
        CheckConstraint(
            "alert_type IN ('财报异动', '评级调整', '技术突破', '格局变化', '政策催化')",
            name="chk_chain_alert_type",
        ),
        CheckConstraint("severity BETWEEN 1 AND 3", name="chk_chain_alert_severity"),
    )
