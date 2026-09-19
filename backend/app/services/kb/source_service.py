"""知识库（kb_source）服务：CRUD、存储聚合、软删与恢复。

软删口径：``deleted_at`` 打标即从列表隐藏，24h 恢复窗内可 restore；
COS/ES 的物理清理由 ``kb-cleanup`` internal 任务扫过期行执行（批次 E 接线）。
存储大小即时增减：``storage_bytes`` 登记字节数聚合，未完成清理期间叠加
``pending_cleanup_bytes`` 展示。
"""

from datetime import timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KB_SOFT_DELETE_RECOVERY_HOURS
from app.core.clock import utc_now
from app.core.exceptions import ConflictError, NotFoundError
from app.core.locking import redis_lock
from app.models.kb import KbSource
from app.repositories.kb import media_repository, source_repository
from app.schemas.kb import KbSourceCreateRequest, KbSourceResponse, KbSourceUpdateRequest
from app.services.admin.audit_service import record_audit

logger = structlog.get_logger(__name__)

AUDIT_SOURCE_CREATE = "kb.source.create"
AUDIT_SOURCE_UPDATE = "kb.source.update"
AUDIT_SOURCE_DELETE = "kb.source.delete"
AUDIT_SOURCE_RESTORE = "kb.source.restore"


def to_view(row: KbSource) -> KbSourceResponse:
    """ORM → wire 视图。"""
    return KbSourceResponse(
        id=row.id,
        source_type=row.source_type,
        name=row.name,
        author=row.author,
        description=row.description,
        enabled=row.enabled,
        storage_bytes=row.storage_bytes,
        pending_cleanup_bytes=row.pending_cleanup_bytes,
        deleted_at=row.deleted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_sources(session: AsyncSession) -> list[KbSourceResponse]:
    """知识库列表（隐藏软删行）。"""
    rows = await source_repository.list_sources(session)
    return [to_view(row) for row in rows]


async def get_source(session: AsyncSession, source_id: int) -> KbSource:
    """读取单个知识库，缺失抛 404（软删行视为不存在，恢复走 restore）。"""
    row = await source_repository.get(session, source_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(f"知识库 {source_id} 不存在")
    return row


async def create_source(
    session: AsyncSession,
    data: KbSourceCreateRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbSourceResponse:
    """新建知识库。"""
    row = KbSource(
        source_type=data.source_type,
        name=data.name,
        author=data.author,
        description=data.description,
        enabled=data.enabled,
    )
    session.add(row)
    await session.flush()
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_SOURCE_CREATE,
        detail={"sourceId": row.id, "sourceType": row.source_type, "name": row.name},
        ip=ip,
    )
    await session.commit()
    await session.refresh(row)
    logger.info("kb_source_created", source_id=row.id, source_type=row.source_type)
    return to_view(row)


async def update_source(
    session: AsyncSession,
    source_id: int,
    data: KbSourceUpdateRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbSourceResponse:
    """编辑知识库基础信息。"""
    row = await get_source(session, source_id)
    if data.name is not None:
        row.name = data.name
    if data.author is not None:
        row.author = data.author
    if data.description is not None:
        row.description = data.description
    if data.enabled is not None:
        row.enabled = data.enabled
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_SOURCE_UPDATE,
        detail={"sourceId": source_id, **data.model_dump(exclude_unset=True)},
        ip=ip,
    )
    await session.commit()
    await session.refresh(row)
    return to_view(row)


async def soft_delete_source(
    session: AsyncSession, source_id: int, *, actor_id: int, ip: str | None = None
) -> None:
    """软删知识库：列表隐藏 + 全部存活素材计入待清理字节。"""
    async with redis_lock(f"kb:source-delete:{source_id}", ttl=60, blocking=False) as ok:
        if not ok:
            raise ConflictError("该知识库正在删除中，请稍后")
        row = await get_source(session, source_id)
        medias = await media_repository.list_by_source(session, source_id)
        now = utc_now()
        pending = sum(m.file_size or 0 for m in medias if m.deleted_at is None)
        for media in medias:
            if media.deleted_at is None:
                media.deleted_at = now
        row.deleted_at = now
        row.storage_bytes = max(0, (row.storage_bytes or 0) - pending)
        row.pending_cleanup_bytes = (row.pending_cleanup_bytes or 0) + pending
        await record_audit(
            session,
            actor_id=actor_id,
            action=AUDIT_SOURCE_DELETE,
            detail={"sourceId": source_id, "mediaCount": len(medias), "pendingBytes": pending},
            ip=ip,
        )
        await session.commit()
        logger.info(
            "kb_source_soft_deleted",
            source_id=source_id,
            media_count=len(medias),
            pending_bytes=pending,
        )


async def restore_source(
    session: AsyncSession, source_id: int, *, actor_id: int, ip: str | None = None
) -> KbSourceResponse:
    """恢复窗内撤销软删（源与全部同期软删素材一起恢复）。"""
    row = await source_repository.get(session, source_id)
    if row is None or row.deleted_at is None:
        raise NotFoundError(f"知识库 {source_id} 不在恢复窗内")
    window = timedelta(hours=KB_SOFT_DELETE_RECOVERY_HOURS)
    if utc_now() - row.deleted_at > window:
        raise NotFoundError("已超过 24 小时恢复窗口，等待清理任务执行")
    row.deleted_at = None
    row.storage_bytes = (row.storage_bytes or 0) + (row.pending_cleanup_bytes or 0)
    row.pending_cleanup_bytes = 0
    medias = await media_repository.list_by_source(
        session, source_id, include_deleted=True
    )
    for media in medias:
        media.deleted_at = None
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_SOURCE_RESTORE,
        detail={"sourceId": source_id, "mediaCount": len(medias)},
        ip=ip,
    )
    await session.commit()
    logger.info("kb_source_restored", source_id=source_id, media_count=len(medias))
    return to_view(row)
