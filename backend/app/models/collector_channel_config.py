"""SQLAlchemy ORM model for collector channel configurations."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CollectorChannelConfig(Base):
    """Configurable data source channel managed by admins."""

    __tablename__ = "collector_channel_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supported_data_types: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
