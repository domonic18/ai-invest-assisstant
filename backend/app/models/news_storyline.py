"""事件故事线（news_storyline 家族）的 SQLAlchemy ORM 模型。

表结构真源是幂等 SQL 迁移（docker/database/migrations/），本模型仅做映射。
故事线为全局内容（AI 建线 + 手动建线共用一张表）；用户级「停止跟踪」
只影响本人视图（user_news_storyline），AI 续接全局进行。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class NewsStoryline(Base):
    """事件故事线（全局）：同一事件多篇报道聚合，origin 区分 AI/手动建线。"""

    __tablename__ = "news_storyline"
    __table_args__ = (
        CheckConstraint(
            "status IN ('tracking', 'near_end', 'finished')",
            name="chk_news_storyline_status",
        ),
        CheckConstraint(
            "origin IN ('ai', 'manual')", name="chk_news_storyline_origin"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="tracking")
    origin: Mapped[str] = mapped_column(String(8), nullable=False, default="ai")
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=True
    )
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    latest_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    nodes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class UserNewsStoryline(Base):
    """用户级跟踪操作（active=默认跟踪中，stopped=本人不再展示）。"""

    __tablename__ = "user_news_storyline"
    __table_args__ = (
        CheckConstraint(
            "action IN ('active', 'stopped')", name="chk_user_news_storyline_action"
        ),
        # 复合主键 (user_id, storyline_id) 见迁移 DDL
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    storyline_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("news_storyline.id", ondelete="CASCADE"),
        primary_key=True,
    )
    action: Mapped[str] = mapped_column(String(8), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class NewsStorylineItem(Base):
    """线内条目：一条资讯至多入一条线（UQ(source, item_id) 保证续接幂等）。"""

    __tablename__ = "news_storyline_item"
    __table_args__ = (
        UniqueConstraint("source", "item_id", name="uq_news_storyline_item_item"),
    )

    storyline_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("news_storyline.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
