"""用户大盘综述编辑副本仓储：读取、按分区 overlay、upsert。"""

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_market_review import UserMarketReview


async def find(
    session: AsyncSession, *, user_id: int, trade_date: date
) -> UserMarketReview | None:
    """按 (user_id, trade_date) 查询用户编辑副本。"""
    stmt = select(UserMarketReview).where(
        UserMarketReview.user_id == user_id,
        UserMarketReview.trade_date == trade_date,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_sections(
    session: AsyncSession,
    *,
    user_id: int,
    trade_date: date,
    sections: dict[str, Any],
    model: str | None,
    generated_at: datetime | None,
    base_review_id: int | None,
) -> None:
    """按 (user_id, trade_date) upsert 编辑副本（不 commit）。

    走 PostgreSQL ``INSERT ... ON CONFLICT DO UPDATE``，等价于原 raw SQL；
    updated_at 由默认值自动维护（ON CONFLICT 路径需显式更新）。
    """
    stmt = insert(UserMarketReview).values(
        user_id=user_id,
        trade_date=trade_date,
        sections=sections,
        model=model,
        generated_at=generated_at,
        base_review_id=base_review_id,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "trade_date"],
        set_={
            "sections": stmt.excluded.sections,
            "model": stmt.excluded.model,
            "generated_at": stmt.excluded.generated_at,
            "base_review_id": stmt.excluded.base_review_id,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    await session.execute(stmt)
