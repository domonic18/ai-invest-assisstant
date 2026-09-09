"""事件故事线仓储：候选查询、建线、幂等续接与用户级操作。"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NEWS_SOURCE_TELEGRAPH
from app.models.news_ai_score import NewsAiScore
from app.models.news_storyline import (
    NewsStoryline,
    NewsStorylineItem,
    UserNewsStoryline,
)
from app.models.news_telegraph import NewsTelegraph

SOURCE_TELEGRAPH = NEWS_SOURCE_TELEGRAPH


async def list_telegraph_candidates(
    session: AsyncSession,
    *,
    limit: int,
    window_hours: int = 48,
    min_score: int = 70,
) -> list[Any]:
    """取近 window_hours 小时高分（≥min_score）且未入任何故事线的电报候选。

    返回行含电报字段与 ai_score（新消息优先）。
    """
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    in_story = (
        select(NewsStorylineItem.item_id)
        .where(
            NewsStorylineItem.source == SOURCE_TELEGRAPH,
            NewsStorylineItem.item_id == cast(NewsTelegraph.cls_msg_id, String),
        )
        .exists()
    )
    stmt = (
        select(NewsTelegraph, NewsAiScore.score)
        .join(
            NewsAiScore,
            (NewsAiScore.source == SOURCE_TELEGRAPH)
            & (NewsAiScore.item_id == cast(NewsTelegraph.cls_msg_id, String)),
        )
        .where(
            ~in_story,
            NewsAiScore.score >= min_score,
            NewsTelegraph.publish_time > since,
        )
        .order_by(NewsTelegraph.publish_time.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.all())


async def list_open_lines(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> list[NewsStoryline]:
    """取续接中的既有线（tracking/near_end，供 LLM 判断新报道归属）。"""
    stmt = (
        select(NewsStoryline)
        .where(NewsStoryline.status.in_(["tracking", "near_end"]))
        .order_by(NewsStoryline.last_seen_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def insert_storyline(
    session: AsyncSession,
    *,
    title: str,
    summary: str | None,
    status: str,
    origin: str,
    user_id: int | None,
    first_seen_at: datetime,
    last_seen_at: datetime,
    latest_brief: str | None,
    nodes: list[dict[str, Any]] | None,
) -> int:
    """插入故事线并返回新 id（不 commit）。"""
    storyline = NewsStoryline(
        title=title,
        summary=summary,
        status=status,
        origin=origin,
        user_id=user_id,
        report_count=0,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        latest_brief=latest_brief,
        nodes=nodes,
    )
    session.add(storyline)
    await session.flush()
    return storyline.id


async def attach_items(
    session: AsyncSession,
    *,
    storyline_id: int,
    refs: list[dict[str, str]],
) -> int:
    """把 (source, item_id) 幂等挂入线内（已被其他线占用或重复挂入均跳过）。

    Returns:
        实际新挂入条数（不 commit）。
    """
    if not refs:
        return 0
    stmt = pg_insert(NewsStorylineItem).values(
        [{"storyline_id": storyline_id, "source": ref["source"], "item_id": ref["item_id"]}
         for ref in refs]
    )
    stmt = stmt.on_conflict_do_nothing()
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def refresh_progress(
    session: AsyncSession,
    *,
    storyline_id: int,
    status: str,
    latest_brief: str | None,
    nodes: list[dict[str, Any]] | None,
    last_seen_at: datetime,
) -> None:
    """按线内实际条数回写计数与进度字段，节点链整列覆写（不 commit）。"""
    count = (
        await session.execute(
            select(func.count())
            .select_from(NewsStorylineItem)
            .where(NewsStorylineItem.storyline_id == storyline_id)
        )
    ).scalar_one()
    storyline = await session.get(NewsStoryline, storyline_id)
    if storyline is None:
        return
    storyline.report_count = int(count)
    storyline.last_seen_at = last_seen_at
    storyline.status = status
    if latest_brief is not None:
        storyline.latest_brief = latest_brief
    if nodes is not None:
        storyline.nodes = nodes


async def get_telegraph(
    session: AsyncSession,
    item_id: str,
) -> NewsTelegraph | None:
    """按业务主键取电报行（手动建线取标题/发布时间）。"""
    stmt = select(NewsTelegraph).where(
        NewsTelegraph.cls_msg_id.cast(String) == item_id
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def find_item_line(
    session: AsyncSession,
    *,
    source: str,
    item_id: str,
) -> NewsStoryline | None:
    """取某条资讯所在的故事线（一条资讯至多入一条线）。"""
    stmt = (
        select(NewsStoryline)
        .join(
            NewsStorylineItem,
            NewsStorylineItem.storyline_id == NewsStoryline.id,
        )
        .where(NewsStorylineItem.source == source, NewsStorylineItem.item_id == item_id)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def upsert_user_action(
    session: AsyncSession,
    *,
    user_id: int,
    storyline_id: int,
    action: str,
) -> None:
    """用户级跟踪操作 upsert（active/stopped，不 commit）。"""
    stmt = pg_insert(UserNewsStoryline).values(
        user_id=user_id, storyline_id=storyline_id, action=action
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "storyline_id"],
        set_={"action": stmt.excluded.action, "updated_at": datetime.now(timezone.utc)},
    )
    await session.execute(stmt)


async def list_today_highlights(
    session: AsyncSession,
    *,
    day_start: datetime,
    min_score: int = 70,
    limit: int = 20,
) -> list[Any]:
    """今日 score≥min_score 电报（分降序），行含 (电报, score, score_detail)。"""
    stmt = (
        select(NewsTelegraph, NewsAiScore.score, NewsAiScore.score_detail)
        .join(
            NewsAiScore,
            and_(
                NewsAiScore.source == SOURCE_TELEGRAPH,
                NewsAiScore.item_id == cast(NewsTelegraph.cls_msg_id, String),
            ),
        )
        .where(NewsAiScore.score >= min_score, NewsTelegraph.publish_time >= day_start)
        .order_by(NewsAiScore.score.desc(), NewsTelegraph.publish_time.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.all())


async def list_focus_storylines(
    session: AsyncSession,
    *,
    user_id: int,
    limit: int = 50,
) -> list[Any]:
    """重点视图线列表：AI 线全局 + 本人 manual 线，排除本人已停止跟踪的线。

    行为 (storyline, user_action)，user_action 取自本人 user_news_storyline。
    """
    stmt = (
        select(NewsStoryline, UserNewsStoryline.action)
        .outerjoin(
            UserNewsStoryline,
            and_(
                UserNewsStoryline.storyline_id == NewsStoryline.id,
                UserNewsStoryline.user_id == user_id,
            ),
        )
        .where(
            or_(
                NewsStoryline.origin == "ai",
                and_(
                    NewsStoryline.origin == "manual",
                    NewsStoryline.user_id == user_id,
                ),
            ),
            or_(
                UserNewsStoryline.action.is_(None),
                UserNewsStoryline.action != "stopped",
            ),
        )
        .order_by(NewsStoryline.last_seen_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.all())


async def get_storyline(
    session: AsyncSession,
    storyline_id: int,
) -> NewsStoryline | None:
    """按 id 取故事线。"""
    return await session.get(NewsStoryline, storyline_id)


async def get_user_action(
    session: AsyncSession,
    *,
    user_id: int,
    storyline_id: int,
) -> str | None:
    """取本人对某线的跟踪操作（无记录为 None）。"""
    stmt = select(UserNewsStoryline.action).where(
        UserNewsStoryline.user_id == user_id,
        UserNewsStoryline.storyline_id == storyline_id,
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def list_storyline_items(
    session: AsyncSession,
    *,
    storyline_id: int,
) -> list[Any]:
    """线内条目（JOIN 电报回显 + AI 分），按发布时间升序。

    行为 (storyline_item, telegraph | None, score | None)。
    """
    stmt = (
        select(NewsStorylineItem, NewsTelegraph, NewsAiScore.score)
        .outerjoin(
            NewsTelegraph,
            and_(
                NewsStorylineItem.source == SOURCE_TELEGRAPH,
                NewsStorylineItem.item_id == cast(NewsTelegraph.cls_msg_id, String),
            ),
        )
        .outerjoin(
            NewsAiScore,
            and_(
                NewsAiScore.source == NewsStorylineItem.source,
                NewsAiScore.item_id == NewsStorylineItem.item_id,
            ),
        )
        .where(NewsStorylineItem.storyline_id == storyline_id)
        .order_by(NewsTelegraph.publish_time.asc())
    )
    result = await session.execute(stmt)
    return list(result.all())
