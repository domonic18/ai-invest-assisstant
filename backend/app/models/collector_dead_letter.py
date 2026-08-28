"""采集任务死信队列的 SQLAlchemy ORM 模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CollectorDeadLetter(Base):
    """采集任务死信队列。

    用于存放重试耗尽后仍失败的任务，便于人工排查与重跑。
    """

    __tablename__ = "collector_dead_letter"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    collector_log_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
