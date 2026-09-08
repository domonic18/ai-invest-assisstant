"""财联社电报查询仓储。"""

from datetime import datetime

from sqlalchemy import String, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NEWS_SOURCE_TELEGRAPH
from app.models.news_ai_score import NewsAiScore
from app.models.news_telegraph import NewsTelegraph

_SOURCE_TELEGRAPH = NEWS_SOURCE_TELEGRAPH

TelegraphRow = tuple[NewsTelegraph, int | None, datetime | None]

_score_join = and_(
    NewsAiScore.source == _SOURCE_TELEGRAPH,
    NewsAiScore.item_id == cast(NewsTelegraph.cls_msg_id, String),
)


async def list_telegraph(
    session: AsyncSession,
    page: int,
    page_size: int,
    category: str | None = None,
    min_importance: int | None = None,
    min_ai_score: int | None = None,
) -> tuple[list[TelegraphRow], int]:
    """分页查询电报（publish_time 降序），左联 AI 分级取 (score, scored_at)。

    Args:
        session: 数据库会话。
        page: 页码（1 起）。
        page_size: 每页条数。
        category: 分类精确筛选（None 不过滤）。
        min_importance: 重要度下限筛选（None 不过滤）。
        min_ai_score: AI 重要度下限筛选（None 不过滤，过滤时仅含已分级条目）。

    Returns:
        ((电报行, ai_score, ai_scored_at) 列表, 总条数)。
    """
    conditions = []
    if category:
        conditions.append(NewsTelegraph.category == category)
    if min_importance is not None:
        conditions.append(NewsTelegraph.importance >= min_importance)
    if min_ai_score is not None:
        conditions.append(NewsAiScore.score >= min_ai_score)

    stmt = select(
        NewsTelegraph, NewsAiScore.score, NewsAiScore.scored_at
    ).select_from(NewsTelegraph)
    count_stmt = select(func.count()).select_from(NewsTelegraph)
    if min_ai_score is not None:
        stmt = stmt.join(NewsAiScore, _score_join)
        count_stmt = count_stmt.join(NewsAiScore, _score_join)
    else:
        stmt = stmt.outerjoin(NewsAiScore, _score_join)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = (
        stmt.order_by(NewsTelegraph.publish_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.execute(stmt)).all())
    return [(row[0], row[1], row[2]) for row in rows], int(total)


async def today_overview(
    session: AsyncSession,
    *,
    day_start: datetime,
) -> tuple[int, datetime | None]:
    """自 day_start 起的 (条数, 最新发布时间)，渠道监控卡用。"""
    scope = NewsTelegraph.publish_time >= day_start
    total = int(
        (
            await session.execute(select(func.count()).select_from(NewsTelegraph).where(scope))
        ).scalar_one()
    )
    latest = (
        await session.execute(select(func.max(NewsTelegraph.publish_time)).where(scope))
    ).scalar_one_or_none()
    return total, latest
