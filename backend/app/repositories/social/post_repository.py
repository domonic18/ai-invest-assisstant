"""内容与情绪判断仓储（social_post / social_sentiment 数据访问与 feed 查询）。"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.constants.social import SOCIAL_STRONG_CONFIDENCE
from app.models.social import SocialAccount, SocialPost, SocialSentiment

# 库存判新的 video_id 集合上限（单账号小时级增量，500 足够覆盖续拉窗口）
VIDEO_ID_SCAN_LIMIT = 500


async def list_video_ids(
    session: AsyncSession, account_id: int, *, limit: int = VIDEO_ID_SCAN_LIMIT
) -> list[str]:
    """账号已有内容的 video_id（判新库存，新内容优先）。"""
    result = await session.execute(
        select(SocialPost.video_id)
        .where(SocialPost.account_id == account_id)
        .order_by(SocialPost.published_at.desc())
        .limit(limit)
    )
    return [row for row in result.scalars().all()]


async def list_pending_posts(
    session: AsyncSession, *, limit: int
) -> list[SocialPost]:
    """待判内容（judged_at IS NULL，启用账号，新内容优先）。

    新内容优先使偶发毒丸条目随新内容流入沉出批量窗口，不阻塞管道。
    """
    result = await session.execute(
        select(SocialPost)
        .join(SocialAccount, SocialPost.account_id == SocialAccount.id)
        .where(SocialPost.judged_at.is_(None), SocialAccount.is_active.is_(True))
        .order_by(SocialPost.published_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def upsert_sentiments(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """批量写入判断结果（post_id 唯一键 DO NOTHING——已判永不重判；不 commit）。"""
    if not rows:
        return 0
    stmt = pg_insert(SocialSentiment).on_conflict_do_nothing(index_elements=["post_id"])
    await session.execute(stmt, rows)
    return len(rows)


async def mark_judged(
    session: AsyncSession, post_ids: list[int], judged_at: datetime
) -> None:
    """标记已判并立即清稿（transcript_text 判后即清，合规边界；不 commit）。"""
    if not post_ids:
        return
    await session.execute(
        update(SocialPost)
        .where(SocialPost.id.in_(post_ids))
        .values(judged_at=judged_at, transcript_text=None)
    )


async def list_stale_transcript_ids(
    session: AsyncSession, *, stale_days: int, limit: int = 500
) -> list[int]:
    """滞留超期的临时文稿 id（判前失败/反复重试的残留）。"""
    stale_before = datetime.now(timezone.utc) - timedelta(days=stale_days)
    result = await session.execute(
        select(SocialPost.id)
        .where(SocialPost.transcript_text.is_not(None), SocialPost.created_at < stale_before)
        .limit(limit)
    )
    return list(result.scalars().all())


async def clear_transcripts(session: AsyncSession, post_ids: list[int]) -> None:
    """清理滞留文稿（不 commit）。"""
    if not post_ids:
        return
    await session.execute(
        update(SocialPost).where(SocialPost.id.in_(post_ids)).values(transcript_text=None)
    )


# ============ 用户侧查询（feed / 账号卡 / 时间线 / ASR 记账） ============


def _feed_row(row: Any) -> dict[str, Any]:
    """(post, account, sentiment) 联查行 → feed 卡片字典。"""
    post, account, sentiment = row
    return {
        "post_id": post.id,
        "video_id": post.video_id,
        "platform": post.platform,
        "account_id": account.id,
        "account_alias": account.alias,
        "category": account.category,
        "title": post.title,
        "caption": post.caption,
        "topic_tags": post.topic_tags,
        "cover_url": post.cover_url,
        "duration_seconds": post.duration_seconds,
        "published_at": post.published_at,
        "digg_count": post.digg_count,
        "comment_count": post.comment_count,
        "share_count": post.share_count,
        "transcript_missing": post.transcript_status != "ok",
        "is_relevant": sentiment.is_relevant,
        "stance": sentiment.stance,
        "confidence": sentiment.confidence,
        "core_arguments": sentiment.core_arguments,
        "targets": sentiment.targets,
        "summary": sentiment.summary,
    }


async def list_feed(
    session: AsyncSession,
    *,
    category: str | None = None,
    stance: str | None = None,
    hours: int | None = None,
    strong_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """情绪流分页（仅启用账号的相关判断，新内容优先）。"""
    conditions: list[ColumnElement[bool]] = [
        SocialSentiment.is_relevant.is_(True),
        SocialAccount.is_active.is_(True),
    ]
    if category:
        conditions.append(SocialAccount.category == category)
    if stance:
        conditions.append(SocialSentiment.stance == stance)
    if hours:
        conditions.append(
            SocialPost.published_at >= datetime.now(timezone.utc) - timedelta(hours=hours)
        )
    if strong_only:
        conditions.append(SocialSentiment.confidence >= SOCIAL_STRONG_CONFIDENCE)
    base = (
        select(SocialPost, SocialAccount, SocialSentiment)
        .join(SocialAccount, SocialPost.account_id == SocialAccount.id)
        .join(SocialSentiment, SocialSentiment.post_id == SocialPost.id)
        .where(*conditions)
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await session.execute(
            base.order_by(SocialPost.published_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return [_feed_row(row) for row in rows], total or 0


async def list_account_cards(
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """账号维度卡（近 7 日多空分布 + 最新判断摘要，启用账号）。"""
    from app.repositories.social import account_repository

    accounts = await account_repository.list_accounts(session, active_only=True)
    if not accounts:
        return []
    ids = [a.id for a in accounts]
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    count_rows = (
        await session.execute(
            select(SocialPost.account_id, SocialSentiment.stance, func.count())
            .join(SocialSentiment, SocialSentiment.post_id == SocialPost.id)
            .where(
                SocialPost.account_id.in_(ids),
                SocialPost.published_at >= seven_days_ago,
                SocialSentiment.is_relevant.is_(True),
            )
            .group_by(SocialPost.account_id, SocialSentiment.stance)
        )
    ).all()
    counts: dict[tuple[int, str], int] = {
        (account_id, stance): n for account_id, stance, n in count_rows
    }

    latest_rows = (
        await session.execute(
            select(SocialPost, SocialSentiment)
            .join(SocialSentiment, SocialSentiment.post_id == SocialPost.id)
            .where(
                SocialPost.account_id.in_(ids),
                SocialSentiment.is_relevant.is_(True),
            )
            .distinct(SocialPost.account_id)
            .order_by(SocialPost.account_id, SocialPost.published_at.desc())
        )
    ).all()
    latest = {row[0].account_id: row for row in latest_rows}

    cards: list[dict[str, Any]] = []
    for account in accounts:
        card: dict[str, Any] = {
            "id": account.id,
            "alias": account.alias,
            "category": account.category,
            "last_post_at": account.last_post_at,
            "bullish_count_7d": counts.get((account.id, "bullish"), 0),
            "bearish_count_7d": counts.get((account.id, "bearish"), 0),
            "neutral_count_7d": counts.get((account.id, "neutral"), 0),
        }
        row = latest.get(account.id)
        if row is not None:
            post, sentiment = row
            card.update(
                {
                    "latest_stance": sentiment.stance,
                    "latest_confidence": sentiment.confidence,
                    "latest_summary": sentiment.summary,
                    "latest_cover_url": post.cover_url,
                }
            )
        cards.append(card)
    return cards


async def list_timeline(
    session: AsyncSession,
    account_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """单账号已判相关内容时间线（新内容优先，立场轨迹由前端派生）。"""
    base = (
        select(SocialPost, SocialSentiment)
        .join(SocialSentiment, SocialSentiment.post_id == SocialPost.id)
        .where(
            SocialPost.account_id == account_id,
            SocialSentiment.is_relevant.is_(True),
        )
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await session.execute(
            base.order_by(SocialPost.published_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        {
            "post_id": post.id,
            "video_id": post.video_id,
            "title": post.title,
            "published_at": post.published_at,
            "stance": sentiment.stance,
            "confidence": sentiment.confidence,
            "summary": sentiment.summary,
            "transcript_missing": post.transcript_status != "ok",
        }
        for post, sentiment in rows
    ]
    return items, total or 0


async def count_transcripts_since(
    session: AsyncSession, since: datetime
) -> dict[str, int]:
    """按转写状态统计 since 之后的入库内容（ASR 今日记账）。"""
    rows = (
        await session.execute(
            select(SocialPost.transcript_status, func.count())
            .where(SocialPost.created_at >= since)
            .group_by(SocialPost.transcript_status)
        )
    ).all()
    return {status: n for status, n in rows}


# ============ 管理端排查查询 ============


async def list_admin_posts(
    session: AsyncSession, account_id: int, *, limit: int = 30
) -> list[dict[str, Any]]:
    """账号最近作品排查行（新内容优先；未判/未入流也在列）。

    返回不含 transcript_text（合规边界：判后即清的临时文稿不出服务层），
    转写降级原因从 transcript_meta 提取为 transcript_reason。
    """
    rows = (
        await session.execute(
            select(SocialPost, SocialSentiment)
            .join(SocialSentiment, SocialSentiment.post_id == SocialPost.id, isouter=True)
            .where(SocialPost.account_id == account_id)
            .order_by(SocialPost.published_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "video_id": post.video_id,
            "title": post.title,
            "published_at": post.published_at,
            "transcript_status": post.transcript_status,
            "transcript_reason": (post.transcript_meta or {}).get("reason"),
            "judged_at": post.judged_at,
            "is_relevant": sentiment.is_relevant if sentiment is not None else None,
            "stance": sentiment.stance if sentiment is not None else None,
            "confidence": sentiment.confidence if sentiment is not None else None,
        }
        for post, sentiment in rows
    ]
