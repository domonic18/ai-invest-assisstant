"""知识点审核服务（F-KB-03，管理端工作台后端）。

职责：章节树查看/发布、知识点列表（状态计数）、白名单修订、
通过/驳回/合并/人工新增。状态流转：

- draft --approve--> published（置 ``embedding_dirty``，批次 E 据此入索引）
- draft|published --reject--> rejected（原 published 置脏，批次 E 删索引文档）
- 修订仅开放 title/point_type/body/term_definition/applicable_scene/
  chapter_path——excerpt 与时间码/页码是溯源锚点，不可改（schema
  ``extra="forbid"`` 显式 422）

仅 published 参与检索（批次 E）；本批不写 ES。
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbPointStatus
from app.core.clock import utc_now
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.kb import KbKnowledgePoint
from app.repositories.kb import media_repository, point_repository
from app.schemas.kb import (
    KbBatchApproveResult,
    KbChapterNode,
    KbChaptersPublishRequest,
    KbChaptersResponse,
    KbKnowledgePointResponse,
    KbPointCounts,
    KbPointCreateRequest,
    KbPointListResponse,
    KbPointPatchRequest,
    KbPointRejectRequest,
    KbPointsBatchApproveRequest,
    KbPointsMergeRequest,
)
from app.services.admin.audit_service import record_audit
from app.services.kb.source_service import get_source

logger = structlog.get_logger(__name__)

AUDIT_CHAPTERS_PUBLISH = "kb.chapters.publish"
AUDIT_POINT_PATCH = "kb.point.patch"
AUDIT_POINT_APPROVE = "kb.point.approve"
AUDIT_POINT_REJECT = "kb.point.reject"
AUDIT_POINT_MERGE = "kb.point.merge"
AUDIT_POINT_CREATE = "kb.point.create"


# ---------------------------------------------------------------------------
# 章节树
# ---------------------------------------------------------------------------


async def get_chapters(
    session: AsyncSession, source_id: int
) -> KbChaptersResponse:
    """读取知识源目录树（draft 供编辑，published 为生效版本）。"""
    source = await get_source(session, source_id)
    tree = dict(source.chapter_tree or {})
    return KbChaptersResponse(
        draft=_to_nodes(tree.get("draft")),
        published=_to_nodes(tree.get("published")),
    )


async def publish_chapters(
    session: AsyncSession,
    source_id: int,
    data: KbChaptersPublishRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbChaptersResponse:
    """整棵发布：published 覆盖写并同步 draft（后续编辑基于已发布版本）。"""
    source = await get_source(session, source_id)
    _validate_tree(data.chapters)
    published = [node.model_dump() for node in data.chapters]
    source.chapter_tree = {"draft": published, "published": published}
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_CHAPTERS_PUBLISH,
        detail={
            "sourceId": source_id,
            "topLevelCount": len(data.chapters),
        },
        ip=ip,
    )
    await session.commit()
    logger.info("kb_chapters_published", source_id=source_id, admin_id=actor_id)
    return KbChaptersResponse(
        draft=_to_nodes(published), published=_to_nodes(published)
    )


def _to_nodes(raw: Any) -> list[KbChapterNode] | None:
    if raw is None:
        return None
    return [KbChapterNode.model_validate(node) for node in raw]


def _validate_tree(chapters: list[KbChapterNode]) -> None:
    """节点 id 唯一、标题非空（层级深度由前端控件约束为两级）。"""
    seen: set[str] = set()

    def walk(nodes: list[KbChapterNode], prefix: str) -> None:
        for node in nodes:
            if not node.title.strip():
                raise UnprocessableEntityError(f"章节 {prefix} 标题不能为空")
            if node.id in seen:
                raise UnprocessableEntityError(f"章节节点 id 重复：{node.id}")
            seen.add(node.id)
            walk(node.children, node.id)

    walk(chapters, "root")


# ---------------------------------------------------------------------------
# 知识点
# ---------------------------------------------------------------------------


def to_view(
    point: KbKnowledgePoint,
    *,
    episode_no: int | None = None,
    media_title: str | None = None,
) -> KbKnowledgePointResponse:
    """ORM → wire 视图。"""
    return KbKnowledgePointResponse(
        id=point.id,
        source_id=point.source_id,
        media_id=point.media_id,
        episode_no=episode_no,
        media_title=media_title,
        point_type=point.point_type,
        title=point.title,
        body=point.body,
        term_definition=point.term_definition,
        applicable_scene=point.applicable_scene,
        excerpt=point.excerpt,
        start_ms=point.start_ms,
        end_ms=point.end_ms,
        page_start=point.page_start,
        page_end=point.page_end,
        related_ids=list(point.related_ids or []),
        chapter_path=[str(p) for p in point.chapter_path or []],
        status=point.status,
        needs_review=point.needs_review,
        review_note=point.review_note,
        reviewed_at=point.reviewed_at,
        created_at=point.created_at,
        updated_at=point.updated_at,
    )


async def _get_point(session: AsyncSession, point_id: int) -> KbKnowledgePoint:
    row = await point_repository.get(session, point_id)
    if row is None:
        raise NotFoundError(f"知识点 {point_id} 不存在")
    return row


async def list_points(
    session: AsyncSession,
    source_id: int,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> KbPointListResponse:
    """知识点分页列表 + 状态计数（审核工作台首屏）。"""
    await get_source(session, source_id)
    by_status = await point_repository.count_by_status(session, source_id)
    counts = KbPointCounts(
        draft=by_status.get(KbPointStatus.DRAFT, 0),
        published=by_status.get(KbPointStatus.PUBLISHED, 0),
        rejected=by_status.get(KbPointStatus.REJECTED, 0),
        needs_review=await point_repository.count_needs_review(session, source_id),
    )
    total = await point_repository.count_by_source(
        session, source_id, status=status
    )
    rows = await point_repository.list_by_source(
        session, source_id, status=status,
        offset=(page - 1) * page_size, limit=page_size,
    )
    return KbPointListResponse(
        items=[
            to_view(point, episode_no=episode_no, media_title=media_title)
            for point, episode_no, media_title in rows
        ],
        total=total,
        counts=counts,
    )


async def patch_point(
    session: AsyncSession,
    point_id: int,
    data: KbPointPatchRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbKnowledgePointResponse:
    """白名单修订（excerpt/定位字段由 schema extra=forbid 拒绝为 422）。"""
    row = await _get_point(session, point_id)
    payload = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in payload.items():
        setattr(row, field, value)
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_POINT_PATCH,
        detail={"pointId": point_id, "fields": sorted(payload.keys())},
        ip=ip,
    )
    await session.commit()
    return await _view_with_media(session, row)


async def approve_point(
    session: AsyncSession,
    point_id: int,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbKnowledgePointResponse:
    """通过：→ published 并置 ``embedding_dirty``（批次 E 索引依据）。"""
    row = await _get_point(session, point_id)
    if row.status == KbPointStatus.PUBLISHED:
        return await _view_with_media(session, row)
    from_status = row.status
    row.status = KbPointStatus.PUBLISHED
    row.needs_review = False
    row.review_note = None
    row.reviewed_by = actor_id
    row.reviewed_at = utc_now()
    row.embedding_dirty = True
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_POINT_APPROVE,
        detail={"pointId": point_id, "fromStatus": from_status},
        ip=ip,
    )
    await session.commit()
    logger.info("kb_point_approved", point_id=point_id, admin_id=actor_id)
    return await _view_with_media(session, row)


async def approve_points(
    session: AsyncSession,
    data: KbPointsBatchApproveRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbBatchApproveResult:
    """批量通过：单事务逐张置 published 并逐张审计；已发布/不存在幂等跳过。"""
    rows = (
        (await session.execute(select(KbKnowledgePoint).where(KbKnowledgePoint.id.in_(data.ids))))
        .scalars()
        .all()
    )
    by_id = {row.id: row for row in rows}
    approved = skipped = 0
    for point_id in data.ids:
        row = by_id.get(point_id)
        if row is None or row.status == KbPointStatus.PUBLISHED:
            skipped += 1
            continue
        from_status = row.status
        row.status = KbPointStatus.PUBLISHED
        row.needs_review = False
        row.review_note = None
        row.reviewed_by = actor_id
        row.reviewed_at = utc_now()
        row.embedding_dirty = True
        await record_audit(
            session,
            actor_id=actor_id,
            action=AUDIT_POINT_APPROVE,
            detail={"pointId": point_id, "fromStatus": from_status},
            ip=ip,
        )
        approved += 1
    await session.commit()
    logger.info(
        "kb_points_batch_approved",
        total=len(data.ids),
        approved=approved,
        skipped=skipped,
        admin_id=actor_id,
    )
    return KbBatchApproveResult(approved=approved, skipped=skipped)


async def reject_point(
    session: AsyncSession,
    point_id: int,
    data: KbPointRejectRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbKnowledgePointResponse:
    """驳回：理由入 review_note；原 published 置脏（批次 E 删索引文档）。"""
    row = await _get_point(session, point_id)
    was_published = row.status == KbPointStatus.PUBLISHED
    row.status = KbPointStatus.REJECTED
    row.review_note = data.reason
    row.reviewed_by = actor_id
    row.reviewed_at = utc_now()
    if was_published:
        row.embedding_dirty = True
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_POINT_REJECT,
        detail={"pointId": point_id, "reason": data.reason},
        ip=ip,
    )
    await session.commit()
    return await _view_with_media(session, row)


async def merge_points(
    session: AsyncSession,
    data: KbPointsMergeRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbKnowledgePointResponse:
    """重复草稿合并：related 并集进目标，源行硬删（仅 draft 可并入）。"""
    target = await _get_point(session, data.target_id)
    source_ids = [pid for pid in data.source_ids if pid != target.id]
    rows = []
    for pid in source_ids:
        row = await _get_point(session, pid)
        if row.source_id != target.source_id:
            raise ConflictError(f"知识点 {pid} 与目标不在同一知识库")
        if row.status != KbPointStatus.DRAFT or target.status != KbPointStatus.DRAFT:
            raise ConflictError("仅草稿状态的知识点可合并")
        rows.append(row)
    related = set(target.related_ids or [])
    related.update(pid for row in rows for pid in (row.related_ids or []))
    related.discard(target.id)
    related.difference_update(source_ids)
    target.related_ids = sorted(related)
    await point_repository.delete_by_ids(session, source_ids)
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_POINT_MERGE,
        detail={"targetId": target.id, "mergedIds": source_ids},
        ip=ip,
    )
    await session.commit()
    return await _view_with_media(session, target)


async def create_point(
    session: AsyncSession,
    data: KbPointCreateRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbKnowledgePointResponse:
    """人工新增（status=draft，走同一审核流；excerpt 缺省取 body 前 200 字）。"""
    media = await media_repository.get(session, data.media_id)
    if media is None or media.deleted_at is not None:
        raise NotFoundError(f"素材 {data.media_id} 不存在")
    await get_source(session, media.source_id)
    row = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type=data.point_type,
        title=data.title,
        body=data.body,
        term_definition=data.term_definition,
        applicable_scene=data.applicable_scene,
        excerpt=data.excerpt or data.body[:200],
        start_ms=data.start_ms,
        end_ms=data.end_ms,
        page_start=data.page_start,
        page_end=data.page_end,
        related_ids=[],
        chapter_path=list(data.chapter_path),
        status=KbPointStatus.DRAFT,
        needs_review=False,
        embedding_dirty=False,
    )
    session.add(row)
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_POINT_CREATE,
        detail={"mediaId": data.media_id, "title": data.title},
        ip=ip,
    )
    await session.commit()
    return await _view_with_media(session, row)


async def _view_with_media(
    session: AsyncSession, point: KbKnowledgePoint
) -> KbKnowledgePointResponse:
    """重新读取 join 冗余（episode/media_title）后出视图。"""
    refreshed = await point_repository.get(session, point.id)
    row = refreshed or point
    media = await media_repository.get(session, row.media_id)
    return to_view(
        row,
        episode_no=media.episode_no if media else None,
        media_title=media.title if media else None,
    )
