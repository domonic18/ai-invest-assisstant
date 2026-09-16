"""社媒大 V 情绪 ORM 模型（F-SOC：追踪账号 / 视频内容 / 情绪判断 / ASR 渠道配置）。

合规边界：transcript_text 是判后即清的临时文稿缓存，任何 API 响应模型不得包含。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    REAL,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class SocialAccount(Base):
    """平台级追踪账号清单（全体登录用户共享同一份视图）。"""

    __tablename__ = "social_account"
    __table_args__ = (
        UniqueConstraint("platform", "sec_uid", name="uq_social_account_platform_sec_uid"),
        Index("idx_social_account_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    sec_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    alias: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="finance_kol")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class SocialPost(Base):
    """追踪账号的新发视频内容单元；(platform, video_id) 幂等去重。"""

    __tablename__ = "social_post"
    __table_args__ = (
        UniqueConstraint("platform", "video_id", name="uq_social_post_platform_video"),
        Index("idx_social_post_published", "published_at"),
        Index("idx_social_post_account_published", "account_id", "published_at"),
        Index("idx_social_post_pending", "judged_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("social_account.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    video_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(nullable=True)
    topic_tags: Mapped[list[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    cover_url: Mapped[str | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    digg_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    share_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    transcript_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    transcript_text: Mapped[str | None] = mapped_column(nullable=True)
    transcript_meta: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class SocialSentiment(Base):
    """情绪判断结果（与 post 一对一，已判永不重判）。"""

    __tablename__ = "social_sentiment"
    __table_args__ = (
        UniqueConstraint("post_id", name="uq_social_sentiment_post"),
        Index("idx_social_sentiment_created", "created_at"),
        Index("idx_social_sentiment_stance_created", "stance", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("social_post.id", ondelete="CASCADE"), nullable=False
    )
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stance: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(REAL, nullable=False)
    core_arguments: Mapped[list[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    targets: Mapped[list[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AsrChannelConfig(Base):
    """ASR 转写服务渠道配置（单行表，管理端「社媒追踪」维护）。"""

    __tablename__ = "asr_channel_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="minimax")
    base_url: Mapped[str] = mapped_column(String(200), nullable=False, default="https://api.minimaxi.com")
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="asr-1.0")
    api_key_encrypted: Mapped[str | None] = mapped_column(nullable=True)
    api_key_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
    )
    hotwords: Mapped[list[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    max_audio_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
