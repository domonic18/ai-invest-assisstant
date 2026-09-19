"""素材（kb_media）服务：上传 init/uploaded、哈希去重、集号管理、软删。

上传链路（arch/12 §3）：

1. ``init_uploads`` 批量建行（course 按序自动编号）+ 预签名 PUT，浏览器直传 COS；
2. ``confirm_uploaded`` 服务端 HEAD 核对 size/etag(md5) → 同库同哈希 409 →
   核验通过记 ``file_size`` 并累加 ``storage_bytes``；
3. 删除为软删（与 kb_source 同 24h 恢复窗），字节从 ``storage_bytes`` 挪入
   ``pending_cleanup_bytes``，物理清理归 ``kb-cleanup`` 任务。

预签名 URL 使用公网 endpoint 签名（minio_service 内部处理），有效期 6 小时。
"""

import re
from datetime import timedelta
from pathlib import PurePosixPath

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_SOFT_DELETE_RECOVERY_HOURS,
)
from app.core.clock import utc_now
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.kb import KbMedia
from app.repositories.kb import media_repository, source_repository
from app.schemas.kb import (
    KbMediaInitRequest,
    KbMediaInitResponse,
    KbMediaInitResult,
    KbMediaPatchRequest,
    KbMediaResponse,
)
from app.services.admin.audit_service import record_audit
from app.services.common.minio_service import get_minio_service
from app.services.kb.source_service import get_source

logger = structlog.get_logger(__name__)

_PRESIGN_TTL_SECONDS = 6 * 3600
_UNSAFE_NAME = re.compile(r"[^0-9A-Za-z._-]+")

AUDIT_MEDIA_INIT = "kb.media.init"
AUDIT_MEDIA_UPLOADED = "kb.media.uploaded"
AUDIT_MEDIA_PATCH = "kb.media.patch"
AUDIT_MEDIA_DELETE = "kb.media.delete"
AUDIT_MEDIA_RESTORE = "kb.media.restore"


def _sanitize_file_name(raw: str) -> str:
    """保留 basename 并收敛为安全文件名（COS key 与展示共用）。"""
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


async def init_uploads(
    session: AsyncSession,
    source_id: int,
    data: KbMediaInitRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbMediaInitResponse:
    """批量建行 + 预签名 PUT。

    集号：course 未显式给 ``episode_no`` 的条目按请求顺序自动编号（max+1 起）；
    book 一律 None。请求内同哈希或同集号立即拒绝，库内冲突对已建行回滚报 409。

    Raises:
        NotFoundError: 知识库不存在。
        ConflictError: 与库内既有素材同哈希 / 集号冲突。
    """
    await get_source(session, source_id)
    minio = get_minio_service()

    seen_hashes: set[str] = set()
    seen_episodes: set[int] = set()
    for item in data.items:
        if item.hash in seen_hashes:
            raise ConflictError(f"文件 {item.file_name} 与本次批内其他文件哈希重复")
        seen_hashes.add(item.hash)
        if item.episode_no is not None:
            if item.episode_no in seen_episodes:
                raise ConflictError(f"文件 {item.file_name} 的集号 {item.episode_no} 批内重复")
            seen_episodes.add(item.episode_no)

    existing = await media_repository.list_by_source(session, source_id)
    existing_hashes = {m.file_hash for m in existing}
    conflict = sorted(seen_hashes & existing_hashes)
    if conflict:
        raise ConflictError(f"该知识库已存在相同内容的素材（哈希 {conflict[0][:8]}…）")
    next_episode = await media_repository.max_episode_no(session, source_id) + 1

    results: list[KbMediaInitResult] = []
    created: list[KbMedia] = []
    try:
        for item in data.items:
            episode_no = item.episode_no
            if episode_no is None and item.media_kind != "book":
                episode_no = next_episode
                next_episode += 1
            if episode_no is not None:
                if episode_no in {m.episode_no for m in existing}:
                    raise ConflictError(f"集号 {episode_no} 已被其他素材占用")
                seen_episodes.add(episode_no)
            title = item.title or PurePosixPath(item.file_name.rsplit(".", 1)[0]).name
            row = KbMedia(
                source_id=source_id,
                media_kind=item.media_kind,
                episode_no=episode_no,
                title=title,
                file_name=_sanitize_file_name(item.file_name),
                cos_key=f"kb/{source_id}/pending/{_sanitize_file_name(item.file_name)}",
                file_size=0,
                file_hash=item.hash,
                duration_seconds=item.duration_seconds,
                page_count=item.page_count,
            )
            session.add(row)
            await session.flush()
            row.cos_key = _cos_key(source_id, row.id, row.file_name)
            created.append(row)
        await record_audit(
            session,
            actor_id=actor_id,
            action=AUDIT_MEDIA_INIT,
            detail={
                "sourceId": source_id,
                "mediaIds": [m.id for m in created],
                "fileNames": [m.file_name for m in created],
            },
            ip=ip,
        )
        await session.commit()
    except ConflictError:
        await session.rollback()
        raise

    for row in created:
        upload_url = await minio.presigned_put_url(
            row.cos_key, expires=timedelta(seconds=_PRESIGN_TTL_SECONDS)
        )
        results.append(
            KbMediaInitResult(
                media_id=row.id,
                file_name=row.file_name,
                cos_key=row.cos_key,
                upload_url=upload_url,
            )
        )
    logger.info(
        "kb_media_init", source_id=source_id, count=len(created)
    )
    return KbMediaInitResponse(items=results)


async def confirm_uploaded(
    session: AsyncSession, media_id: int, *, actor_id: int, ip: str | None = None
) -> KbMediaResponse:
    """uploaded 回调：HEAD 核对 + 哈希去重 + 字节入账。

    Raises:
        UnprocessableEntityError: 对象缺失或 size/etag 与登记不符（孤儿对象删除）。
        ConflictError: 同库已有相同哈希素材。
    """
    row = await get_media(session, media_id)
    minio = get_minio_service()
    stat = await minio.stat_object(row.cos_key)
    if stat is None:
        raise UnprocessableEntityError("对象尚未上传完成或已被清理，请重新上传")
    size, etag = stat
    if etag and row.file_hash.lower() not in (etag, etag.replace("-", "")):
        await minio.remove_files([row.cos_key])
        raise UnprocessableEntityError(
            "上传内容校验失败（etag 与登记 md5 不符），已清除孤儿对象，请重试上传"
        )
    conflict = await media_repository.find_hash_conflict(
        session, row.source_id, row.file_hash, exclude_id=row.id
    )
    if conflict is not None:
        await minio.remove_files([row.cos_key])
        raise ConflictError(
            f"与既有素材「{conflict.title}」（第 {conflict.episode_no or '-'} 集）内容重复"
        )
    row.file_size = size
    source = await source_repository.get(session, row.source_id)
    assert source is not None
    source.storage_bytes = (source.storage_bytes or 0) + size
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_MEDIA_UPLOADED,
        detail={"mediaId": row.id, "size": size, "cosKey": row.cos_key},
        ip=ip,
    )
    await session.commit()
    logger.info(
        "kb_media_uploaded", media_id=row.id, size=size, cos_key=row.cos_key
    )
    return to_view(row)


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
    row.deleted_at = None
    source = await source_repository.get(session, row.source_id)
    assert source is not None
    source.pending_cleanup_bytes = max(
        0, (source.pending_cleanup_bytes or 0) - (row.file_size or 0)
    )
    source.storage_bytes = (source.storage_bytes or 0) + (row.file_size or 0)
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
