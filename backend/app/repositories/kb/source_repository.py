"""kb_source 仓储查询（不 commit）。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb import KbMedia, KbSource


async def get(session: AsyncSession, source_id: int) -> KbSource | None:
    """按 ID 读取（含已软删行，恢复窗口需要）。"""
    return await session.get(KbSource, source_id)


async def list_sources(
    session: AsyncSession, *, include_deleted: bool = False
) -> list[KbSource]:
    """知识库列表（默认隐藏软删行，updated_at 倒序）。"""
    stmt = select(KbSource).order_by(KbSource.updated_at.desc())
    if not include_deleted:
        stmt = stmt.where(KbSource.deleted_at.is_(None))
    return list((await session.execute(stmt)).scalars().all())


async def count_active_media(session: AsyncSession, source_id: int) -> int:
    """未软删素材数（源列表展示规模用）。"""
    stmt = (
        select(func.count())
        .select_from(KbMedia)
        .where(KbMedia.source_id == source_id, KbMedia.deleted_at.is_(None))
    )
    return int((await session.execute(stmt)).scalar_one())
