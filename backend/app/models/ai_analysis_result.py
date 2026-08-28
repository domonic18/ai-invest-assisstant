"""AI 分析结果记录的 SQLAlchemy ORM 模型。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AiAnalysisResult(Base):
    """AI 分析结果原始记录表。"""

    __tablename__ = "ai_analysis_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, nullable=False
    )
    skill_id: Mapped[str] = mapped_column(String(50), nullable=False)
    stock_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_output: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
