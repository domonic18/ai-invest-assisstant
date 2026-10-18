"""用户组模型：按组开通功能模块。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class UserGroup(Base):
    """用户组表。"""

    __tablename__ = "user_group"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    permissions: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
