"""AI 任务级模型绑定的 SQLAlchemy ORM 模型。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class LLMTaskBinding(Base):
    """任务槽位 → llm_config 条目绑定；无行 = 该任务跟随系统默认对话模型。

    config_id 无 FK：引用有效性（存在/启用/purpose=chat）由服务层写侧校验；
    读侧绑定条目失效时降级系统默认并告警（调度可用性优先）。
    """

    __tablename__ = "llm_task_binding"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    config_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
