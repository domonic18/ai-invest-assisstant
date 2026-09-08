"""资讯 AI 分级仓储：跨源通用标注表读写。"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, cast, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NEWS_SOURCE_TELEGRAPH
from app.models.news_ai_score import NewsAiScore
from app.models.news_telegraph import NewsTelegraph

SOURCE_TELEGRAPH = NEWS_SOURCE_TELEGRAPH


async def list_unscored_telegraph(
    session: AsyncSession,
    *,
    limit: int,
    window_days: int = 3,
) -> list[NewsTelegraph]:
    """取近 window_days 天未分级的电报（新消息优先）。"""
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    scored = (
        select(NewsAiScore.item_id)
        .where(
            NewsAiScore.source == SOURCE_TELEGRAPH,
            NewsAiScore.item_id == cast(NewsTelegraph.cls_msg_id, String),
        )
        .exists()
    )
    stmt = (
        select(NewsTelegraph)
        .where(~scored, NewsTelegraph.publish_time > since)
        .order_by(NewsTelegraph.publish_time.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def upsert_scores(
    session: AsyncSession,
    rows: list[dict[str, Any]],
) -> int:
    """批量写入评分（同条重评覆盖 score/detail/scored_at，不 commit）。"""
    if not rows:
        return 0
    stmt = pg_insert(NewsAiScore).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "item_id"],
        set_={
            "score": stmt.excluded.score,
            "score_detail": stmt.excluded.score_detail,
            "scored_at": stmt.excluded.scored_at,
        },
    )
    await session.execute(stmt)
    return len(rows)


async def score_map(
    session: AsyncSession,
    *,
    source: str,
    item_ids: list[str],
) -> dict[str, tuple[int, datetime]]:
    """批量取指定条目的 (score, scored_at)，用于列表回填。"""
    if not item_ids:
        return {}
    stmt = select(NewsAiScore.item_id, NewsAiScore.score, NewsAiScore.scored_at).where(
        NewsAiScore.source == source, NewsAiScore.item_id.in_(item_ids)
    )
    result = await session.execute(stmt)
    return {row.item_id: (row.score, row.scored_at) for row in result.all()}


async def today_stats(
    session: AsyncSession,
    *,
    day_start: datetime,
) -> tuple[int, int, int]:
    """今日（北京日界）电报统计：(总数, 已分级, 高重要度 score>=70)。"""
    today_ids = select(cast(NewsTelegraph.cls_msg_id, String)).where(
        NewsTelegraph.publish_time >= day_start
    )
    total = (
        await session.execute(
            select(func.count())
            .select_from(NewsTelegraph)
            .where(NewsTelegraph.publish_time >= day_start)
        )
    ).scalar_one()
    scored = (
        await session.execute(
            select(func.count())
            .select_from(NewsAiScore)
            .where(
                NewsAiScore.source == SOURCE_TELEGRAPH,
                NewsAiScore.item_id.in_(today_ids),
            )
        )
    ).scalar_one()
    high = (
        await session.execute(
            select(func.count())
            .select_from(NewsAiScore)
            .where(
                NewsAiScore.source == SOURCE_TELEGRAPH,
                NewsAiScore.score >= 70,
                NewsAiScore.item_id.in_(today_ids),
            )
        )
    ).scalar_one()
    return int(total), int(scored), int(high)
