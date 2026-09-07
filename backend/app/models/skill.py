"""skill / user_skill 表的 SQLAlchemy ORM 模型。

表结构真源是幂等 SQL 迁移（docker/database/migrations/），本模型仅做映射。
builtin 行由启动时 ``sync_builtin_skills`` 从 ``app/skills/registry.py``
幂等同步写入；custom 行由用户经 API 创建（``custom_definition`` 存配置非代码）。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class Skill(Base):
    """技能登记行：builtin（registry 同步）或 custom（用户定义）。"""

    __tablename__ = "skill"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('executable', 'prompt_only', 'doc_only', 'custom')",
            name="chk_skill_kind",
        ),
        UniqueConstraint("skill_id", name="uq_skill_skill_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=True
    )
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    custom_definition: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class UserSkill(Base):
    """用户安装关系：skill_id 指向 skill.skill_id（unique 列），删 skill 级联删安装。"""

    __tablename__ = "user_skill"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uq_user_skill_user_skill"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("skill.skill_id", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
