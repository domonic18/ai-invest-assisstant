"""知识库域的 SQLAlchemy ORM 模型（arch/12）。

知识源（kb_source）、素材（kb_media）、内容分段（kb_transcript_segment）、
知识点（kb_knowledge_point）、图片资产（kb_image_asset）与域设置单行
（kb_settings）。
PG 是唯一存储，检索列（embedding halfvec 向量 +
pg_trgm 词面生成列）同库内嵌，无投影层。
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.kb import KB_EMBEDDING_DIMS, KbDescribeStatus, KbProcessStatus
from app.core.clock import utc_now
from app.core.database import Base

_JSONB = JSONB().with_variant(JSON(), "sqlite")
# sqlite（单测）侧退化为 JSON 文本存 list，PG 侧走 pgvector 真实类型
_HALFVEC = HALFVEC(KB_EMBEDDING_DIMS).with_variant(JSON(), "sqlite")


class KbSource(Base):
    """知识源（知识库实例）：课程或电子书集合。"""

    __tablename__ = "kb_source"
    __table_args__ = (Index("idx_kb_source_active", "deleted_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    chapter_tree: Mapped[dict[str, Any]] = mapped_column(
        _JSONB, nullable=False, default=lambda: {"draft": None, "published": None}
    )
    storage_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    pending_cleanup_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class KbMedia(Base):
    """素材：课程的一集视频/音频，或一部书 PDF。"""

    __tablename__ = "kb_media"
    __table_args__ = (
        # 集号唯一仅约束课程（书的 episode_no 为 NULL；PG 侧为部分唯一索引，见迁移）
        Index("uq_kb_media_source_episode", "source_id", "episode_no", unique=True),
        # 哈希去重仅约束存活行（软删行不占哈希位，24h 恢复窗内可重传）
        Index(
            "uq_kb_media_source_hash",
            "source_id",
            "file_hash",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("idx_kb_media_source_status", "source_id", "process_status"),
        Index("idx_kb_media_deleted", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("kb_source.id", ondelete="CASCADE"), nullable=False
    )
    media_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    episode_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    relative_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cos_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_status: Mapped[str] = mapped_column(String(16), nullable=False, default=KbProcessStatus.UPLOADED)
    process_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    process_meta: Mapped[dict[str, Any]] = mapped_column(_JSONB, nullable=False, default=dict)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class KbTranscriptSegment(Base):
    """内容分段：课程句级时间码区间 / 书页区间的一段文本。"""

    __tablename__ = "kb_transcript_segment"
    __table_args__ = (
        Index("uq_kb_segment_media_seq", "media_id", "seq_no", unique=True),
        Index("idx_kb_segment_dirty", "embedding_dirty"),
        Index("idx_kb_segment_source_dirty", "source_id", "embedding_dirty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    media_id: Mapped[int] = mapped_column(
        ForeignKey("kb_media.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("kb_source.id", ondelete="CASCADE"), nullable=False
    )
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(_HALFVEC, nullable=True)
    embedding_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class KbKnowledgePoint(Base):
    """知识点卡片：检索与引用的最小知识单元。"""

    __tablename__ = "kb_knowledge_point"
    __table_args__ = (
        Index("idx_kb_point_source_status", "source_id", "status"),
        Index("idx_kb_point_dirty", "embedding_dirty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("kb_source.id", ondelete="CASCADE"), nullable=False
    )
    media_id: Mapped[int] = mapped_column(
        ForeignKey("kb_media.id", ondelete="CASCADE"), nullable=False
    )
    point_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    term_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_scene: Mapped[str | None] = mapped_column(Text, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    related_ids: Mapped[list[Any]] = mapped_column(_JSONB, nullable=False, default=list)
    chapter_path: Mapped[list[Any]] = mapped_column(_JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(_HALFVEC, nullable=True)
    embedding_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class KbImageAsset(Base):
    """图片资产：书嵌图与课程视频关键帧统一落表（文字搜图的检索载体）。"""

    __tablename__ = "kb_image_asset"
    __table_args__ = (
        Index("idx_kb_image_source_dirty", "source_id", "embedding_dirty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    media_id: Mapped[int] = mapped_column(
        ForeignKey("kb_media.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("kb_source.id", ondelete="CASCADE"), nullable=False
    )
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(_JSONB, nullable=True)
    cos_key: Mapped[str] = mapped_column(String(500), nullable=False)
    thumb_cos_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text_in_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    describe_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=KbDescribeStatus.PENDING
    )
    describe_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(_HALFVEC, nullable=True)
    embedding_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    index_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class KbSettings(Base):
    """知识库域设置（单行）：域参数 + 模型角色槽位（llm_config 引用）。"""

    __tablename__ = "kb_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hotwords: Mapped[list[Any]] = mapped_column(_JSONB, nullable=False, default=list)
    segment_max_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    asr_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    auto_approve_points: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    unit_prices: Mapped[dict[str, Any]] = mapped_column(_JSONB, nullable=False, default=dict)
    embedding_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("llm_config.id", ondelete="SET NULL"), nullable=True
    )
    clean_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("llm_config.id", ondelete="SET NULL"), nullable=True
    )
    extract_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("llm_config.id", ondelete="SET NULL"), nullable=True
    )
    vision_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("llm_config.id", ondelete="SET NULL"), nullable=True
    )
    authorized_user_ids: Mapped[list[Any]] = mapped_column(_JSONB, nullable=False, default=list)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
