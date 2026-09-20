"""kb_knowledge_point 仓储查询（不 commit）。"""

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbPointStatus
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


def _chapter_scope(source_id: int, chapter_path: list[str]) -> list[Any]:
    """消费侧章节浏览的公共过滤（published + 祖先链 containment + 素材存活）。

    位置 id 体系下「包含全部祖先 id」≡ 前缀匹配（抽取管线已按树修剪路径）；
    ``@>`` 由 GIN(jsonb_path_ops) 索引支撑。
    """
    return [
        KbKnowledgePoint.source_id == source_id,
        KbKnowledgePoint.status == KbPointStatus.PUBLISHED,
        KbKnowledgePoint.chapter_path.contains(chapter_path),
        KbMedia.deleted_at.is_(None),
    ]


async def list_published_by_chapter(
    session: AsyncSession,
    source_id: int,
    chapter_path: list[str],
    *,
    offset: int = 0,
    limit: int = 20,
) -> list[tuple[KbKnowledgePoint, int | None, str | None, str]]:
    """章节卡片清单（浏览路径）：episode_no/start_ms/page_start 确定性排序。"""
    stmt = (
        select(
            KbKnowledgePoint, KbMedia.episode_no, KbMedia.title, KbMedia.media_kind
        )
        .join(KbMedia, KbKnowledgePoint.media_id == KbMedia.id)
        .where(*_chapter_scope(source_id, chapter_path))
        .order_by(
            KbMedia.episode_no.asc().nullslast(),
            KbKnowledgePoint.start_ms.asc().nullslast(),
            KbKnowledgePoint.page_start.asc().nullslast(),
            KbKnowledgePoint.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return [
        (row[0], row[1], row[2], row[3])
        for row in (await session.execute(stmt)).all()
    ]


async def count_published_by_chapter(
    session: AsyncSession, source_id: int, chapter_path: list[str]
) -> int:
    """章节卡片计数（浏览分页 total；口径与 list_published_by_chapter 一致）。"""
    stmt = (
        select(func.count())
        .select_from(KbKnowledgePoint)
        .join(KbMedia, KbKnowledgePoint.media_id == KbMedia.id)
        .where(*_chapter_scope(source_id, chapter_path))
    )
    return int((await session.execute(stmt)).scalar_one() or 0)
