"""用户自选股与分组的 SQLAlchemy ORM 模型。"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserWatchlistGroup(Base):
    """用户自选股分组表。"""

    __tablename__ = "user_watchlist_group"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_review_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User")


class UserWatchlist(Base):
    """用户自选股表。"""

    __tablename__ = "user_watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_watchlist_group.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="watchlist")
    group: Mapped["UserWatchlistGroup"] = relationship("UserWatchlistGroup")
