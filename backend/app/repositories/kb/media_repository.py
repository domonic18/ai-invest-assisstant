"""kb_media / kb_transcript_segment 仓储查询（不 commit）。"""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb import KbKnowledgePoint, KbMedia, KbTranscriptSegment


async def get(session: AsyncSession, media_id: int) -> KbMedia | None:
    """按 ID 读取（含软删行）。"""
    return await session.get(KbMedia, media_id)


async def get_by_ids(session: AsyncSession, media_ids: list[int]) -> list[KbMedia]:
    """按 ID 批量读取存活素材（费用闸门批量校验用）。"""
    if not media_ids:
        return []
    stmt = select(KbMedia).where(
        KbMedia.id.in_(media_ids), KbMedia.deleted_at.is_(None)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_by_source(
    session: AsyncSession, source_id: int, *, include_deleted: bool = False
) -> list[KbMedia]:
    """素材列表（默认隐藏软删；集号升序、无集号按创建序）。"""
    stmt = select(KbMedia).where(KbMedia.source_id == source_id)
    if not include_deleted:
        stmt = stmt.where(KbMedia.deleted_at.is_(None))
    stmt = stmt.order_by(KbMedia.episode_no.is_(None), KbMedia.episode_no, KbMedia.id)
    return list((await session.execute(stmt)).scalars().all())


async def max_episode_no(session: AsyncSession, source_id: int) -> int:
    """当前最大集号（自动编号从 max+1 起；无行返回 0）。"""
    stmt = select(func.max(KbMedia.episode_no)).where(KbMedia.source_id == source_id)
    return int((await session.execute(stmt)).scalar_one() or 0)


async def find_hash_conflict(
    session: AsyncSession, source_id: int, file_hash: str, *, exclude_id: int
) -> KbMedia | None:
    """同库同哈希的既有素材（排除自身；软删行不参与去重——重传恢复语义）。"""
    stmt = (
        select(KbMedia)
        .where(
            KbMedia.source_id == source_id,
            KbMedia.file_hash == file_hash,
            KbMedia.id != exclude_id,
            KbMedia.deleted_at.is_(None),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def find_episode_conflict(
    session: AsyncSession,
    source_id: int,
    episode_no: int,
    *,
    exclude_id: int,
) -> KbMedia | None:
    """集号被其他素材占用（软删行仍占位——uq 部分唯一索引同样约束）。"""
    stmt = (
        select(KbMedia)
        .where(
            KbMedia.source_id == source_id,
            KbMedia.episode_no == episode_no,
            KbMedia.id != exclude_id,
            KbMedia.deleted_at.is_(None),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def list_segments(
    session: AsyncSession, media_id: int
) -> list[KbTranscriptSegment]:
    """分段按序读取（文稿编辑器与转写落库共用）。"""
    stmt = (
        select(KbTranscriptSegment)
        .where(KbTranscriptSegment.media_id == media_id)
        .order_by(KbTranscriptSegment.seq_no)
    )
    return list((await session.execute(stmt)).scalars().all())


async def delete_segments(session: AsyncSession, media_id: int) -> None:
    """删除该素材全部分段（重转写覆盖场景；调用方负责 commit）。"""
    await session.execute(
        delete(KbTranscriptSegment).where(KbTranscriptSegment.media_id == media_id)
    )


async def list_queued_media(session: AsyncSession) -> list[KbMedia]:
    """待转写素材（queued 的 video/audio，按创建序）。"""
    stmt = (
        select(KbMedia)
        .where(
            KbMedia.process_status == "queued",
            KbMedia.media_kind.in_(("video", "audio")),
            KbMedia.deleted_at.is_(None),
        )
        .order_by(KbMedia.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_dirty_by_source(
    session: AsyncSession, source_id: int
) -> dict[int, int]:
    """按素材聚合待索引分段数（embedding_dirty=true）。"""
    stmt = (
        select(KbTranscriptSegment.media_id, func.count())
        .where(
            KbTranscriptSegment.source_id == source_id,
            KbTranscriptSegment.embedding_dirty.is_(True),
        )
        .group_by(KbTranscriptSegment.media_id)
    )
    return {mid: int(n) for mid, n in (await session.execute(stmt)).all()}


async def count_points_by_source(
    session: AsyncSession, source_id: int
) -> dict[int, int]:
    """按素材聚合知识点数（知识卡片，不含驳回）。"""
    stmt = (
        select(KbKnowledgePoint.media_id, func.count())
        .where(
            KbKnowledgePoint.source_id == source_id,
            KbKnowledgePoint.status != "rejected",
        )
        .group_by(KbKnowledgePoint.media_id)
    )
    return {mid: int(n) for mid, n in (await session.execute(stmt)).all()}
