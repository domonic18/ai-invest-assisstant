"""内容与情绪判断仓储（social_post / social_sentiment 数据访问，不含 feed 查询）。"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social import SocialPost, SocialSentiment

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
    from app.models.social import SocialAccount

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
