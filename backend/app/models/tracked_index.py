"""跟踪指数配置的 SQLAlchemy ORM 模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrackedIndexConfig(Base):
    """工作台/行情卡跟踪指数清单，Admin CRUD 管理。"""

    __tablename__ = "tracked_index_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    index_name: Mapped[str] = mapped_column(String(100), nullable=False)
    market_category: Mapped[str] = mapped_column(String(10), nullable=False)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
