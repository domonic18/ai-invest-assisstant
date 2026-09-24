"""检索命中水合（arch/12 §7.2 下半）：卡片全字段以 PG 为真相源。

行状态防御过滤兜物化间隙（published/done/未排除/素材存活）；案例卡关联帧
命中区间外扩取帧，分段命中附前滚后起播点；缩略图短时效签名（消费页 15min
口径，管理台 1h 不带入）。召回与融合见 ``search_ranking``，入口编排见
``search_service``。
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbDescribeStatus, KbPointStatus
from app.models.kb import KbImageAsset, KbKnowledgePoint, KbMedia, KbTranscriptSegment
from app.schemas.kb import (
    KbSearchFrameHit,
    KbSearchImageHit,
    KbSearchPointHit,
    KbSearchSegmentHit,
)
from app.services.common.minio_service import get_minio_service

#: 课程命中起播前滚（需求 3~5s 口径取下限）
_SEEK_REWIND_MS = 4000
#: 案例卡片关联帧：命中区间外扩秒数与取帧上限
_CASE_FRAME_PAD_MS = 20_000
_CASE_FRAME_LIMIT = 3
_THUMB_URL_TTL = timedelta(minutes=15)


async def _media_map(session: AsyncSession, media_ids: set[int]) -> dict[int, KbMedia]:
    if not media_ids:
        return {}
    rows = (
        await session.execute(select(KbMedia).where(KbMedia.id.in_(media_ids)))
    ).scalars().all()
    return {row.id: row for row in rows if row.deleted_at is None}


async def _hydrate_points(
    session: AsyncSession,
    ids: list[int],
    scores: dict[str, float],
    *,
    chapter_prefix: tuple[str, ...] | None,
) -> list[KbSearchPointHit]:
    """卡片水合：published/章节前缀精筛（WHERE 是 containment 粗筛）+ 案例卡关联帧。"""
    rows = (
        await session.execute(select(KbKnowledgePoint).where(KbKnowledgePoint.id.in_(ids)))
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    medias = await _media_map(
        session, {row.media_id for row in rows if row.status == KbPointStatus.PUBLISHED}
    )
    hits: list[KbSearchPointHit] = []
    for db_id in ids:
        row = by_id.get(db_id)
        if row is None or row.status != KbPointStatus.PUBLISHED:
            continue
        path = [str(p) for p in row.chapter_path or []]
        if chapter_prefix and tuple(path[: len(chapter_prefix)]) != chapter_prefix:
            continue
        media = medias.get(row.media_id)
        if media is None:
            continue
        frames = (
            await _case_frames(session, media, row)
            if media.media_kind != "book" and row.point_type == "case"
            else []
        )
        hits.append(
            KbSearchPointHit(
                id=row.id,
                source_id=row.source_id,
                media_id=row.media_id,
                media_kind=media.media_kind,
                episode_no=media.episode_no,
                media_title=media.title,
                point_type=row.point_type,
                title=row.title,
                body=row.body,
                term_definition=row.term_definition,
                applicable_scene=row.applicable_scene,
                excerpt=row.excerpt,
                chapter_path=path,
                related_ids=[int(r) for r in row.related_ids or []],
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                page_start=row.page_start,
                page_end=row.page_end,
                score=scores.get(f"point-{row.id}", 0.0),
                frames=frames,
            )
        )
    return hits


async def _case_frames(
    session: AsyncSession, media: KbMedia, point: KbKnowledgePoint
) -> list[KbSearchFrameHit]:
    """案例卡关联帧：命中时间窗外扩取帧（缩略图短时效签名）。"""
    if point.start_ms is None:
        return []
    window_end = point.end_ms if point.end_ms is not None else point.start_ms
    rows = (
        await session.execute(
            select(KbImageAsset)
            .where(
                KbImageAsset.media_id == media.id,
                KbImageAsset.describe_status == KbDescribeStatus.DONE,
                KbImageAsset.index_excluded.is_(False),
                KbImageAsset.start_ms >= point.start_ms - _CASE_FRAME_PAD_MS,
                KbImageAsset.start_ms <= window_end + _CASE_FRAME_PAD_MS,
            )
            .order_by(KbImageAsset.start_ms)
            .limit(_CASE_FRAME_LIMIT)
        )
    ).scalars().all()
    if not rows:
        return []
    minio = get_minio_service()
    hits = []
    for row in rows:
        hits.append(
            KbSearchFrameHit(
                id=row.id,
                start_ms=row.start_ms,
                thumb_url=await minio.get_presigned_url(
                    row.thumb_cos_key or row.cos_key, expires=_THUMB_URL_TTL
                ),
                caption=row.caption,
            )
        )
    return hits


async def _hydrate_segments(
    session: AsyncSession, ids: list[int], scores: dict[str, float]
) -> list[KbSearchSegmentHit]:
    """原文分段水合：附前滚后起播点 seekMs。"""
    rows = (
        await session.execute(
            select(KbTranscriptSegment).where(KbTranscriptSegment.id.in_(ids))
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    medias = await _media_map(session, {row.media_id for row in rows})
    hits: list[KbSearchSegmentHit] = []
    for db_id in ids:
        row = by_id.get(db_id)
        if row is None:
            continue
        media = medias.get(row.media_id)
        if media is None:
            continue
        hits.append(
            KbSearchSegmentHit(
                id=row.id,
                source_id=row.source_id,
                media_id=row.media_id,
                media_kind=media.media_kind,
                episode_no=media.episode_no,
                media_title=media.title,
                text=row.text,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                seek_ms=(
                    max(0, row.start_ms - _SEEK_REWIND_MS)
                    if row.start_ms is not None
                    else None
                ),
                score=scores.get(f"seg-{row.id}", 0.0),
            )
        )
    return hits


async def _hydrate_images(
    session: AsyncSession, ids: list[int], scores: dict[str, float]
) -> list[KbSearchImageHit]:
    """图片命中水合（done 未排除防御过滤，缩略图短时效签名）。"""
    rows = (
        await session.execute(select(KbImageAsset).where(KbImageAsset.id.in_(ids)))
    ).scalars().all()
    by_id = {
        row.id: row
        for row in rows
        if row.describe_status == KbDescribeStatus.DONE and not row.index_excluded
    }
    medias = await _media_map(session, {row.media_id for row in by_id.values()})
    minio = get_minio_service()
    hits: list[KbSearchImageHit] = []
    for db_id in ids:
        row = by_id.get(db_id)
        if row is None:
            continue
        media = medias.get(row.media_id)
        if media is None:
            continue
        hits.append(
            KbSearchImageHit(
                id=row.id,
                source_id=row.source_id,
                media_id=row.media_id,
                media_kind=media.media_kind,
                episode_no=media.episode_no,
                page_no=row.page_no,
                start_ms=row.start_ms,
                text_in_image=row.text_in_image,
                caption=row.caption,
                thumb_url=await minio.get_presigned_url(
                    row.thumb_cos_key or row.cos_key, expires=_THUMB_URL_TTL
                ),
                score=scores.get(f"img-{row.id}", 0.0),
            )
        )
    return hits
