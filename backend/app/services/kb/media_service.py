"""素材（kb_media）服务：行管理（列表/读取/修正/重排队/软删/恢复）。

删除为软删（与 kb_source 同 24h 恢复窗），字节从 ``storage_bytes`` 挪入
``pending_cleanup_bytes``，物理清理归 ``kb-cleanup`` 任务；上传链路
（登记/回调核验/分片会话）见 ``media_upload`` / ``media_upload_session``。
"""

import re
from datetime import timedelta
from pathlib import PurePosixPath

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_SOFT_DELETE_RECOVERY_HOURS,
    KbProcessStatus,
)
from app.core.clock import utc_now
from app.core.exceptions import ConflictError, NotFoundError
from app.models.kb import KbMedia
from app.repositories.kb import media_repository, source_repository
from app.schemas.kb import KbMediaPatchRequest, KbMediaResponse
from app.services.admin.audit_service import record_audit
from app.services.kb import index_service
from app.services.kb.source_service import get_source

logger = structlog.get_logger(__name__)

_UNSAFE_NAME = re.compile(r"[^0-9A-Za-z._-]+")

AUDIT_MEDIA_PATCH = "kb.media.patch"
AUDIT_MEDIA_DELETE = "kb.media.delete"
AUDIT_MEDIA_RESTORE = "kb.media.restore"
AUDIT_MEDIA_REQUEUE = "kb.media.requeue"


def _display_file_name(raw: str) -> str:
    """展示用原始文件名（仅取 basename，不改写字符）。"""
    return PurePosixPath(raw.replace("\\", "/")).name.strip()[:500]


def _sanitize_file_name(raw: str) -> str:
    """COS key 用安全文件名（收敛为 ASCII，对象键不含空白/非 ASCII 字符）。"""
    stem = PurePosixPath(raw.replace("\\", "/")).name
    cleaned = _UNSAFE_NAME.sub("_", stem).strip("._") or "file"
    return cleaned[:200]


def _cos_key(source_id: int, media_id: int, file_name: str) -> str:
    return f"kb/{source_id}/{media_id}/{_sanitize_file_name(file_name)}"


def to_view(
    row: KbMedia, *, point_count: int = 0, dirty_count: int = 0
) -> KbMediaResponse:
    """ORM → wire 视图。"""
    return KbMediaResponse(
        id=row.id,
        source_id=row.source_id,
        media_kind=row.media_kind,
        episode_no=row.episode_no,
        title=row.title,
        file_name=row.file_name,
        relative_path=row.relative_path,
        file_size=row.file_size,
        file_hash=row.file_hash,
        duration_seconds=row.duration_seconds,
        page_count=row.page_count,
        process_status=row.process_status,
        process_error=row.process_error,
        process_meta=row.process_meta or {},
        edited_at=row.edited_at,
        deleted_at=row.deleted_at,
        point_count=point_count,
        dirty_count=dirty_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_media(
    session: AsyncSession, source_id: int
) -> list[KbMediaResponse]:
    """素材列表（隐藏软删行），附带知识点数与待索引分段数。"""
    await get_source(session, source_id)
    rows = await media_repository.list_by_source(session, source_id)
    points = await media_repository.count_points_by_source(session, source_id)
    dirty = await media_repository.count_dirty_by_source(session, source_id)
    return [
        to_view(
            row,
            point_count=points.get(row.id, 0),
            dirty_count=dirty.get(row.id, 0),
        )
        for row in rows
    ]


async def get_media(session: AsyncSession, media_id: int) -> KbMedia:
    """读取素材，缺失或已软删抛 404。"""
    row = await media_repository.get(session, media_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(f"素材 {media_id} 不存在")
    return row


async def patch_media(
    session: AsyncSession,
    media_id: int,
    data: KbMediaPatchRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbMediaResponse:
    """修正集号/标题/时长/页数（集号冲突 409）。"""
    row = await get_media(session, media_id)
    if data.episode_no is not None and data.episode_no != row.episode_no:
        conflict = await media_repository.find_episode_conflict(
            session, row.source_id, data.episode_no, exclude_id=row.id
        )
        if conflict is not None:
            raise ConflictError(f"集号 {data.episode_no} 已被「{conflict.title}」占用")
        row.episode_no = data.episode_no
    if data.title is not None:
        row.title = data.title
    if data.duration_seconds is not None:
        row.duration_seconds = data.duration_seconds
    if data.page_count is not None:
        row.page_count = data.page_count
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_MEDIA_PATCH,
        detail={"mediaId": media_id, **data.model_dump(exclude_unset=True)},
        ip=ip,
    )
    await session.commit()
    return to_view(row)


async def requeue_media(
    session: AsyncSession, media_id: int, *, actor_id: int, ip: str | None = None
) -> KbMediaResponse:
    """失败/卡死素材重新入队（failed/processing → queued）。

    processing 放行是 worker 崩溃恢复通道：进程中断后素材停在 processing，
    list_queued_media 只扫 queued，不放行则永久卡死。活worker 正在处理时
    重排队无副作用——转写互斥锁（blocking=False）使下轮扫描得到 busy，
    当前运行结束时以终态覆盖。
    """
    row = await get_media(session, media_id)
    if row.process_status not in (KbProcessStatus.FAILED, KbProcessStatus.PROCESSING):
        raise ConflictError(
            f"仅失败或处理中的素材可重新转写，当前状态：{row.process_status}"
        )
    row.process_status = KbProcessStatus.QUEUED
    previous_error = row.process_error
    row.process_error = None
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_MEDIA_REQUEUE,
        detail={"mediaId": media_id, "previousError": previous_error},
        ip=ip,
    )
    await session.commit()
    return to_view(row)


async def soft_delete_media(
    session: AsyncSession, media_id: int, *, actor_id: int, ip: str | None = None
) -> None:
    """单集软删：字节挪入待清理，列表隐藏（24h 恢复窗）。"""
    row = await get_media(session, media_id)
    now = utc_now()
    row.deleted_at = now
    source = await source_repository.get(session, row.source_id)
    assert source is not None
    source.storage_bytes = max(0, (source.storage_bytes or 0) - (row.file_size or 0))
    source.pending_cleanup_bytes = (source.pending_cleanup_bytes or 0) + (
        row.file_size or 0
    )
    # 投影同步：子行置脏，下轮 kb-index 删对应文档
    await index_service.mark_media_children_dirty(session, media_id)
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_MEDIA_DELETE,
        detail={"mediaId": media_id, "size": row.file_size or 0},
        ip=ip,
    )
    await session.commit()
    logger.info("kb_media_soft_deleted", media_id=media_id)


async def restore_media(
    session: AsyncSession, media_id: int, *, actor_id: int, ip: str | None = None
) -> KbMediaResponse:
    """恢复窗内撤销单集软删。"""
    row = await media_repository.get(session, media_id)
    if row is None or row.deleted_at is None:
        raise NotFoundError(f"素材 {media_id} 不在恢复窗内")
    window = timedelta(hours=KB_SOFT_DELETE_RECOVERY_HOURS)
    if utc_now() - row.deleted_at > window:
        raise NotFoundError("已超过 24 小时恢复窗口，等待清理任务执行")
    # 存活行哈希唯一（部分索引）：删除期间同内容已重传时恢复会撞键，转为显式冲突
    conflict = await media_repository.find_hash_conflict(
        session, row.source_id, row.file_hash, exclude_id=row.id
    )
    if conflict is not None:
        raise ConflictError(
            f"同内容已重新上传为「{conflict.title}」，无法重复恢复；"
            "请直接删除本条或保留新素材"
        )
    row.deleted_at = None
    source = await source_repository.get(session, row.source_id)
    assert source is not None
    source.pending_cleanup_bytes = max(
        0, (source.pending_cleanup_bytes or 0) - (row.file_size or 0)
    )
    source.storage_bytes = (source.storage_bytes or 0) + (row.file_size or 0)
    # 投影同步：软删期间文档可能已被删，置脏让下轮 kb-index 重新入索引
    await index_service.mark_media_children_dirty(session, media_id)
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_MEDIA_RESTORE,
        detail={"mediaId": media_id},
        ip=ip,
    )
    await session.commit()
    logger.info("kb_media_restored", media_id=media_id)
    return to_view(row)
