"""用户 API Key 模型（多租户 MCP 凭证）。

表结构真源是幂等 SQL 迁移 ``20261029d_create_user_api_key.sql``；
明文 token 不入库，``key_hash`` 是校验唯一依据。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class UserApiKey(Base):
    """用户 API Key 行。"""

    __tablename__ = "user_api_key"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
