"""mcp_server_config 表的 SQLAlchemy ORM 模型。

表结构真源是幂等 SQL 迁移（docker/database/migrations/20260910c_*.sql）。
Phase 2 将在 agent 工具构建时消费 enabled 行注入 MCP 工具。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class McpServerConfig(Base):
    """后台管理的 MCP server 配置。"""

    __tablename__ = "mcp_server_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    transport_type: Mapped[str] = mapped_column(String(10), nullable=False, default="http")
    command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    args: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    env: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    headers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
