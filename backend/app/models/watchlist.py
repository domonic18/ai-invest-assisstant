"""SQLAlchemy ORM models for user watchlist."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserWatchlist(Base):
    """用户自选股表。"""

    __tablename__ = "user_watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="watchlist")
