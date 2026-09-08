"""热点主题快照（news_topic_snapshot）的 SQLAlchemy ORM 模型。

表结构真源是幂等 SQL 迁移（docker/database/migrations/），本模型仅做映射。
盘中/盘后双跑各存一行（PK trade_date+session），LLM 聚类结果 + 库内热度
因子拼装进 topics JSONB；input_hash 同输入跳过重生成。
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class NewsTopicSnapshot(Base):
    """热点主题榜快照（F-AI-03）：主题/情绪/热度构成/传导链。"""

    __tablename__ = "news_topic_snapshot"
    __table_args__ = (
        CheckConstraint(
            "session IN ('intraday', 'post')",
            name="chk_news_topic_snapshot_session",
        ),
    )

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    session: Mapped[str] = mapped_column(String(8), primary_key=True)
    topics: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    wordcloud: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
