"""AI 任务级模型绑定的 SQLAlchemy ORM 模型。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class LLMTaskBinding(Base):
    """任务槽位 → 主/备 llm_config 条目绑定（选择点，2026-11-11 重构）。

    config_id 是必填主模型，backup_config_id 是可选备用（主冷却/失效时
    解析层切备，主备皆不可用 fail loud 抛错）。两列均无 FK：引用有效性
    （存在/启用/purpose 匹配槽位）由服务层写侧校验。
    """

    __tablename__ = "llm_task_binding"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    config_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    backup_config_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
