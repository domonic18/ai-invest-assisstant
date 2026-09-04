"""采集任务执行日志的 SQLAlchemy ORM 模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CollectorLog(Base):
    """采集任务执行日志。"""

    __tablename__ = "collector_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict, nullable=True)
