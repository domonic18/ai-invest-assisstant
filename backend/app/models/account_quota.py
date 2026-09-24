"""账号准入与 AI 用量治理域的 SQLAlchemy ORM 模型（arch/10）。

配额真相源（user_ai_quota）、逐次计量明细（user_token_usage）、
用户自备 Key 配置（user_llm_config）、管理审计（admin_audit_log）
与运行时全局设置（system_setting）。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


def _jsonb() -> Any:
    """JSONB 列（SQLite 测试库降级为 JSON）。"""
    return mapped_column(JSONB().with_variant(JSON(), "sqlite"))


class UserAiQuota(Base):
    """用户一次性 AI token 配额（total_tokens NULL = 不设上限）。"""

    __tablename__ = "user_ai_quota"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    total_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )


class UserTokenUsage(Base):
    """单次模型调用计量明细；user_id NULL = 系统维度（定时任务）。"""

    __tablename__ = "user_token_usage"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    feature: Mapped[str] = mapped_column(String(20), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    outlet: Mapped[str] = mapped_column(String(10), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class UserLlmConfig(Base):
    """用户自备 API Key（BYOK）配置；user_id UNIQUE 物化「同一时间仅一套生效」。"""

    __tablename__ = "user_llm_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AdminAuditLog(Base):
    """管理端审计：审批、配额调整、全局设置变更。"""

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    detail: Mapped[dict[str, Any]] = _jsonb()
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class SystemSetting(Base):
    """运行时可变全局设置 KV（管理端可改，不进 config.py）。"""

    __tablename__ = "system_setting"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[Any] = _jsonb()
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
