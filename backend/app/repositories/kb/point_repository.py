"""kb_knowledge_point 仓储查询（不 commit）。"""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb import KbKnowledgePoint, KbMedia


async def get(session: AsyncSession, point_id: int) -> KbKnowledgePoint | None:
    """按 ID 读取。"""
    return await session.get(KbKnowledgePoint, point_id)


async def list_by_source(
    session: AsyncSession,
    source_id: int,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[tuple[KbKnowledgePoint, int | None, str | None]]:
    """知识点分页列表，附带素材集号与标题（原文脚注展示），id 升序保证翻页稳定。"""
    stmt = (
        select(KbKnowledgePoint, KbMedia.episode_no, KbMedia.title)
        .join(KbMedia, KbKnowledgePoint.media_id == KbMedia.id)
        .where(KbKnowledgePoint.source_id == source_id)
    )
    if status is not None:
        stmt = stmt.where(KbKnowledgePoint.status == status)
    stmt = stmt.order_by(KbKnowledgePoint.id).offset(offset).limit(limit)
    return [(row[0], row[1], row[2]) for row in (await session.execute(stmt)).all()]


async def count_by_source(
    session: AsyncSession, source_id: int, *, status: str | None = None
) -> int:
    """计数（列表 total 用；status None 计全量）。"""
    stmt = (
        select(func.count())
        .select_from(KbKnowledgePoint)
        .where(KbKnowledgePoint.source_id == source_id)
    )
    if status is not None:
        stmt = stmt.where(KbKnowledgePoint.status == status)
    return int((await session.execute(stmt)).scalar_one() or 0)


async def count_by_status(
    session: AsyncSession, source_id: int
) -> dict[str, int]:
    """按状态分组计数（审核工作台 chips）。"""
    stmt = (
        select(KbKnowledgePoint.status, func.count())
        .where(KbKnowledgePoint.source_id == source_id)
        .group_by(KbKnowledgePoint.status)
    )
    return {status: int(n) for status, n in (await session.execute(stmt)).all()}


async def count_needs_review(session: AsyncSession, source_id: int) -> int:
    """待人工复核数（excerpt 未过防线的草稿）。"""
    stmt = (
        select(func.count())
        .select_from(KbKnowledgePoint)
        .where(
            KbKnowledgePoint.source_id == source_id,
            KbKnowledgePoint.needs_review.is_(True),
        )
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def find_titles(
    session: AsyncSession, source_id: int
) -> list[tuple[str, int]]:
    """同库全部知识点的 (title, id)——related_titles 回链映射。"""
    stmt = select(KbKnowledgePoint.title, KbKnowledgePoint.id).where(
        KbKnowledgePoint.source_id == source_id
    )
    return [(title, point_id) for title, point_id in (await session.execute(stmt)).all()]


async def delete_by_ids(session: AsyncSession, point_ids: list[int]) -> None:
    """按 id 硬删（合并去重；仅 draft 调用方校验后传入）。"""
    if not point_ids:
        return
    await session.execute(
        delete(KbKnowledgePoint).where(KbKnowledgePoint.id.in_(point_ids))
    )
