"""K 线画线 ORM 模型（F-DRAW：用户画线 / AI 画线两表）。

锚点存数据坐标 (date, price)，payload JSONB 内为 camelCase 结构
（与 shared/types/drawing.ts 契约同构）；像素坐标禁止落库。
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class UserKlineDrawing(Base):
    """用户画线（per-user 私有，归属键 user_id + target + period，每行一条）。"""

    __tablename__ = "user_kline_drawing"
    __table_args__ = (
        Index("idx_user_kline_drawing_scope", "user_id", "target_type", "target_code", "period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_code: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    drawing_type: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AiKlineDrawing(Base):
    """AI 画线集（per-user 私有、可变工作区，每用户每标的每周期一套）。"""

    __tablename__ = "ai_kline_drawing"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_type", "target_code", "period", name="uq_ai_kline_drawing"
        ),
        Index("idx_ai_kline_drawing_scope", "user_id", "target_type", "target_code", "period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_code: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    drawings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
