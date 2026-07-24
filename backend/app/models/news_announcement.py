"""SQLAlchemy ORM model for news announcements and research reports."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NewsAnnouncement(Base):
    """新闻、公告与研报元数据表。"""

    __tablename__ = "news_announcement"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    publish_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sentiment: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    industry_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True
    )
    elasticsearch_doc_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("source_url"),)
