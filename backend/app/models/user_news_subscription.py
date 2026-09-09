"""我的订阅（user_news_subscription 家族）的 SQLAlchemy ORM 模型。

表结构真源是幂等 SQL 迁移（docker/database/migrations/），本模型仅做映射。
订阅为关键词命中（ILIKE 不耗 LLM），命中写 news_subscription_hit 幂等留痕，
电报流按 (source, item_id) 回填 ★ 标注。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class UserNewsSubscription(Base):
    """用户资讯订阅：关键词 + 可选渠道过滤；push_enabled 实装前仅存配置。"""

    __tablename__ = "user_news_subscription"
    __table_args__ = (
        UniqueConstraint("user_id", "keyword", name="uq_user_news_subscription_user_keyword"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)
    channels: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class NewsSubscriptionHit(Base):
    """订阅命中记录：(subscription, source, item_id) 幂等，hit_at 供最近命中统计。"""

    __tablename__ = "news_subscription_hit"

    subscription_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_news_subscription.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    hit_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
