"""SQLAlchemy ORM model for collector channel data-type priorities."""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.collector_channel_config import CollectorChannelConfig


class CollectorChannelDataType(Base):
    """渠道支持的数据类型及优先级（同 data_type 下 priority 越小越优先）。"""

    __tablename__ = "collector_channel_data_types"
    __table_args__ = (
        UniqueConstraint("channel_id", "data_type", name="uq_ccdt_channel_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("collector_channel_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    channel: Mapped[CollectorChannelConfig] = relationship(lazy="joined")
