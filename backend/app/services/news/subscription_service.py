"""我的订阅服务：关键词命中扫描（定时路径）+ 订阅 CRUD（API 路径）。

命中为关键词包含匹配（不耗 LLM），写 ``news_subscription_hit`` 幂等留痕；
水位（已扫描到的 cls_msg_id）存 Redis，跨轮增量。
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.constants import NEWS_SOURCE_TELEGRAPH
from app.core.exceptions import ConflictError, NotFoundError
from app.models.user_news_subscription import UserNewsSubscription
from app.repositories.news import subscription_repository

logger = structlog.get_logger(__name__)

SOURCE_TELEGRAPH = NEWS_SOURCE_TELEGRAPH

_WATERMARK_KEY = "news:subscription:watermark"
_SCAN_LIMIT = 200


async def match_pending(session: AsyncSession) -> dict[str, Any]:
    """对水位后的电报做关键词命中扫描（每 10 分钟）。

    Returns:
        {matched: 新增命中数, scanned: 扫描条数}；无订阅或无新电报时全零。
    """
    subscriptions = await subscription_repository.list_enabled(session)
    if not subscriptions:
        return {"matched": 0, "scanned": 0}

    watermark = await _load_watermark()
    rows = await subscription_repository.list_telegraph_after(
        session, after_id=watermark, limit=_SCAN_LIMIT
    )
    if not rows:
        return {"matched": 0, "scanned": 0}

    hit_rows: list[dict[str, Any]] = []
    for sub in subscriptions:
        channels = sub.channels or []
        if channels and SOURCE_TELEGRAPH not in channels:
            continue
        keyword = sub.keyword.lower()
        for row in rows:
            haystack = f"{row.title or ''}\n{row.content or ''}".lower()
            if keyword in haystack:
                hit_rows.append(
                    {
                        "subscription_id": sub.id,
                        "source": SOURCE_TELEGRAPH,
                        "item_id": str(row.cls_msg_id),
                    }
                )
    matched = await subscription_repository.insert_hits(session, hit_rows)
    await session.commit()

    new_watermark = max(row.cls_msg_id for row in rows)
    await _save_watermark(new_watermark)
    if matched:
        logger.info("subscription_hits_written", matched=matched, scanned=len(rows))
    return {"matched": matched, "scanned": len(rows)}


async def _load_watermark() -> int:
    raw = await get_redis().get(_WATERMARK_KEY)
    return int(raw) if raw else 0


async def _save_watermark(value: int) -> None:
    await get_redis().set(_WATERMARK_KEY, value)


async def list_for_user(
    session: AsyncSession, *, user_id: int
) -> list[dict[str, Any]]:
    """用户订阅列表 + 每项命中统计（id/keyword/channels/enabled/... + hit_count/last_hit_at）。"""
    stmt = (
        select(UserNewsSubscription)
        .where(UserNewsSubscription.user_id == user_id)
        .order_by(UserNewsSubscription.created_at.desc())
    )
    result = await session.execute(stmt)
    subs = list(result.scalars().all())
    stats = await subscription_repository.hit_stats(
        session, subscription_ids=[sub.id for sub in subs]
    )
    return [
        _as_item(sub, *stats.get(sub.id, (0, None))) for sub in subs
    ]


async def with_hit_stats(
    session: AsyncSession, subscription: UserNewsSubscription
) -> dict[str, Any]:
    """单条订阅回填命中统计（create/update 后的响应组装）。"""
    stats = await subscription_repository.hit_stats(
        session, subscription_ids=[subscription.id]
    )
    return _as_item(subscription, *stats.get(subscription.id, (0, None)))


def _as_item(sub: UserNewsSubscription, hit_count: int, last_hit_at: Any) -> dict[str, Any]:
    return {
        "id": sub.id,
        "keyword": sub.keyword,
        "channels": sub.channels,
        "push_enabled": sub.push_enabled,
        "enabled": sub.enabled,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
        "hit_count": hit_count,
        "last_hit_at": last_hit_at,
    }


async def create(
    session: AsyncSession,
    *,
    user_id: int,
    keyword: str,
    channels: list[str] | None,
) -> UserNewsSubscription:
    """新增订阅（同用户关键词唯一）。"""
    keyword = keyword.strip()
    if not keyword:
        raise ConflictError("关键词不能为空")
    exists = (
        await session.execute(
            select(UserNewsSubscription).where(
                UserNewsSubscription.user_id == user_id,
                UserNewsSubscription.keyword == keyword,
            )
        )
    ).scalars().first()
    if exists is not None:
        raise ConflictError("该关键词已订阅")

    subscription = UserNewsSubscription(
        user_id=user_id, keyword=keyword, channels=channels
    )
    session.add(subscription)
    await session.flush()
    await session.commit()
    return subscription


async def update(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: int,
    channels: list[str] | None = None,
    push_enabled: bool | None = None,
    enabled: bool | None = None,
) -> UserNewsSubscription:
    """更新订阅（归属校验，他人资源 404）。"""
    subscription = await _get_owned(session, user_id=user_id, subscription_id=subscription_id)
    if channels is not None:
        subscription.channels = channels
    if push_enabled is not None:
        subscription.push_enabled = push_enabled
    if enabled is not None:
        subscription.enabled = enabled
    await session.commit()
    return subscription


async def delete(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: int,
) -> None:
    """删除订阅（归属校验，级联删命中记录）。"""
    subscription = await _get_owned(session, user_id=user_id, subscription_id=subscription_id)
    await session.delete(subscription)
    await session.commit()


async def _get_owned(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: int,
) -> UserNewsSubscription:
    stmt = select(UserNewsSubscription).where(
        UserNewsSubscription.id == subscription_id,
        UserNewsSubscription.user_id == user_id,
    )
    subscription = (await session.execute(stmt)).scalars().first()
    if subscription is None:
        raise NotFoundError("订阅不存在")
    return subscription
