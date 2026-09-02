"""财联社电报的 SQLAlchemy ORM 模型。"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NewsTelegraph(Base):
    """财联社电报（stream 驻留进程增量轮询，cls_msg_id 幂等，v1 仅 PG）。"""

    __tablename__ = "news_telegraph"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cls_msg_id: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    importance: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    shared: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    stock_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(20)), nullable=True
    )
    extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=True,
    )
    publish_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("cls_msg_id"),)
