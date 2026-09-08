"""我的订阅仓储：订阅行、命中写入与命中统计。"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_telegraph import NewsTelegraph
from app.models.user_news_subscription import NewsSubscriptionHit, UserNewsSubscription


async def list_enabled(session: AsyncSession) -> list[UserNewsSubscription]:
    """取全部启用中的订阅（跨用户：命中扫描是全局批处理）。"""
    stmt = (
        select(UserNewsSubscription)
        .where(UserNewsSubscription.enabled.is_(True))
        .order_by(UserNewsSubscription.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_telegraph_after(
    session: AsyncSession,
    *,
    after_id: int,
    limit: int,
) -> list[NewsTelegraph]:
    """取水位之后的电报（cls_msg_id 单调递增）。

    after_id<=0 表示首跑无水位：取最新一批（DESC），命中扫描与顺序无关。
    """
    if after_id > 0:
        stmt = (
            select(NewsTelegraph)
            .where(NewsTelegraph.cls_msg_id > after_id)
            .order_by(NewsTelegraph.cls_msg_id.asc())
            .limit(limit)
        )
    else:
        stmt = (
            select(NewsTelegraph)
            .order_by(NewsTelegraph.cls_msg_id.desc())
            .limit(limit)
        )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def insert_hits(
    session: AsyncSession,
    rows: list[dict[str, Any]],
) -> int:
    """幂等写入命中记录（(subscription, source, item_id) 冲突跳过，不 commit）。"""
    if not rows:
        return 0
    stmt = pg_insert(NewsSubscriptionHit).values(rows)
    stmt = stmt.on_conflict_do_nothing()
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def hit_stats(
    session: AsyncSession,
    *,
    subscription_ids: list[int],
) -> dict[int, tuple[int, datetime | None]]:
    """按订阅聚合 (累计命中数, 最近命中时间)，用于订阅列表回填。"""
    if not subscription_ids:
        return {}
    stmt = (
        select(
            NewsSubscriptionHit.subscription_id,
            func.count(),
            func.max(NewsSubscriptionHit.hit_at),
        )
        .where(NewsSubscriptionHit.subscription_id.in_(subscription_ids))
        .group_by(NewsSubscriptionHit.subscription_id)
    )
    result = await session.execute(stmt)
    return {row[0]: (int(row[1]), row[2]) for row in result.all()}


async def hit_item_ids(
    session: AsyncSession,
    *,
    user_id: int,
    source: str,
    item_ids: list[str],
) -> set[str]:
    """当前用户任一启用订阅命中的条目 id 集（电报流 ★ 回填探查）。"""
    if not item_ids:
        return set()
    stmt = (
        select(NewsSubscriptionHit.item_id)
        .join(
            UserNewsSubscription,
            UserNewsSubscription.id == NewsSubscriptionHit.subscription_id,
        )
        .where(
            UserNewsSubscription.user_id == user_id,
            UserNewsSubscription.enabled.is_(True),
            NewsSubscriptionHit.source == source,
            NewsSubscriptionHit.item_id.in_(item_ids),
        )
    )
    result = await session.execute(stmt)
    return {row[0] for row in result.all()}


async def subscribed_exists(
    session: AsyncSession,
    *,
    user_id: int,
    source: str,
    item_id: str,
) -> bool:
    """单条是否命中当前用户订阅（subscription_only 过滤的 EXISTS 语义）。"""
    return bool(
        await hit_item_ids(session, user_id=user_id, source=source, item_ids=[item_id])
    )
