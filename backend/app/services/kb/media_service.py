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
    KbProcessStatus,
)
from app.core.clock import utc_now
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.kb import KbMedia
from app.repositories.kb import media_repository, source_repository
from app.schemas.kb import (
    KbMediaInitRequest,
    KbMediaInitResponse,
    KbMediaInitResult,
    KbMediaPatchRequest,
    KbMediaResponse,
    KbUploadSessionPart,
    KbUploadSessionPartUrl,
    KbUploadSessionRequest,
    KbUploadSessionResponse,
)
from app.services.admin.audit_service import record_audit
from app.services.common.minio_service import (
    MinIOService,
    MultipartPart,
    MultipartSessionNotFoundError,
    get_minio_service,
)
from app.services.kb.source_service import get_source

logger = structlog.get_logger(__name__)

_PRESIGN_TTL_SECONDS = 6 * 3600
_UNSAFE_NAME = re.compile(r"[^0-9A-Za-z._-]+")

AUDIT_MEDIA_INIT = "kb.media.init"
AUDIT_MEDIA_UPLOADED = "kb.media.uploaded"
AUDIT_MEDIA_PATCH = "kb.media.patch"
AUDIT_MEDIA_DELETE = "kb.media.delete"
AUDIT_MEDIA_RESTORE = "kb.media.restore"
AUDIT_MEDIA_SESSION = "kb.media.upload-session"
AUDIT_MEDIA_REQUEUE = "kb.media.requeue"

# process_meta 内分片会话键（confirm 成功或 abort 后清除；declaredSize 保留作审计）
_SESSION_META_KEYS = ("uploadId", "partSize", "partCount", "sessionStartedAt")


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
    book 一律 None。请求内同哈希或同集号立即拒绝（409，整批回滚）。
    库内同哈希为文件级冲突：不抛 409，该条目返回 conflictWith（既有素材标题），
    mediaId/cosKey/uploadUrl 为 None，其余条目照常登记——批量重传时已存在的
    文件只影响自身，不拖垮整批。从未上传成功字节的孤儿行（0 字节）同哈希
    直接收养复用（保留原集号）。结果与请求 items 等长同序。

    Raises:
        NotFoundError: 知识库不存在。
        ConflictError: 批内同哈希 / 同集号 / 与既有素材集号冲突。
    """
    await get_source(session, source_id)
    minio = get_minio_service()

    seen_hashes: dict[str, str] = {}
    seen_episodes: set[int] = set()
    for item in data.items:
        first = seen_hashes.get(item.hash)
        if first is not None:
            raise ConflictError(
                f"文件 {item.file_name} 与本次批内的 {first} 内容完全相同"
                "（哈希重复），请删除重复副本后重试"
            )
        seen_hashes[item.hash] = item.file_name
        if item.episode_no is not None:
            if item.episode_no in seen_episodes:
                raise ConflictError(f"文件 {item.file_name} 的集号 {item.episode_no} 批内重复")
            seen_episodes.add(item.episode_no)

    existing = await media_repository.list_by_source(session, source_id)
    orphan_by_hash: dict[str, KbMedia] = {
        m.file_hash: m
        for m in existing
        if m.deleted_at is None
        and m.process_status == "uploaded"
        and m.file_size == 0
    }
    blocked_by_hash: dict[str, KbMedia] = {
        m.file_hash: m for m in existing if m.file_hash not in orphan_by_hash
    }
    next_episode = await media_repository.max_episode_no(session, source_id) + 1

    pending: list[KbMediaInitResult | KbMedia] = []
    adopted_ids: list[int] = []
    skipped_names: list[str] = []
    try:
        for item in data.items:
            blocked = blocked_by_hash.get(item.hash)
            if blocked is not None:
                pending.append(
                    KbMediaInitResult(
                        file_name=item.file_name,
                        conflict_with=(
                            f"已有素材「{blocked.title}」"
                            f"（第 {blocked.episode_no or '-'} 集）"
                        ),
                    )
                )
                skipped_names.append(item.file_name)
                continue
            orphan = orphan_by_hash.get(item.hash)
            if orphan is not None:
                orphan.media_kind = item.media_kind
                orphan.title = (
                    item.title or PurePosixPath(item.file_name.rsplit(".", 1)[0]).name
                )
                orphan.file_name = _display_file_name(item.file_name)
                orphan.relative_path = item.relative_path
                orphan.duration_seconds = item.duration_seconds
                orphan.page_count = item.page_count
                orphan.cos_key = _cos_key(source_id, orphan.id, item.file_name)
                orphan.process_meta = {
                    **(orphan.process_meta or {}),
                    "declaredSize": item.size,
                }
                pending.append(orphan)
                adopted_ids.append(orphan.id)
                continue
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
                file_name=_display_file_name(item.file_name),
                relative_path=item.relative_path,
                cos_key=f"kb/{source_id}/pending/{_sanitize_file_name(item.file_name)}",
                file_size=0,
                file_hash=item.hash,
                duration_seconds=item.duration_seconds,
                page_count=item.page_count,
                process_meta={"declaredSize": item.size},
            )
            session.add(row)
            await session.flush()
            row.cos_key = _cos_key(source_id, row.id, row.file_name)
            pending.append(row)
        await record_audit(
            session,
            actor_id=actor_id,
            action=AUDIT_MEDIA_INIT,
            detail={
                "sourceId": source_id,
                "mediaIds": [m.id for m in pending if isinstance(m, KbMedia)],
                "fileNames": [
                    m.file_name for m in pending if isinstance(m, KbMedia)
                ],
                "adoptedMediaIds": adopted_ids,
                "skippedConflicts": skipped_names,
            },
            ip=ip,
        )
        await session.commit()
    except ConflictError:
        await session.rollback()
        raise

    results: list[KbMediaInitResult] = []
    for entry in pending:
        if isinstance(entry, KbMedia):
            upload_url = await minio.presigned_put_url(
                entry.cos_key, expires=timedelta(seconds=_PRESIGN_TTL_SECONDS)
            )
            results.append(
                KbMediaInitResult(
                    media_id=entry.id,
                    file_name=entry.file_name,
                    cos_key=entry.cos_key,
                    upload_url=upload_url,
                )
            )
        else:
            results.append(entry)
    logger.info(
        "kb_media_init",
        source_id=source_id,
        count=len(results) - len(skipped_names),
        adopted=len(adopted_ids),
        skipped=len(skipped_names),
    )
    return KbMediaInitResponse(items=results)


async def confirm_uploaded(
    session: AsyncSession, media_id: int, *, actor_id: int, ip: str | None = None
) -> KbMediaResponse:
    """uploaded 回调：multipart 合并或 HEAD 核对 + 哈希去重 + 字节入账。

    单 PUT 路径以 etag(md5) 核对内容；multipart 路径合并前按服务端 list_parts
    汇总核对 declaredSize（分片 etag 由浏览器逐片核对，合并后 etag 不再是整文件
    md5，只核对象总大小）。

    Raises:
        UnprocessableEntityError: 对象缺失或 size/etag 与登记不符（孤儿对象删除）。
        ConflictError: 同库已有相同哈希素材。
    """
    row = await get_media(session, media_id)
    minio = get_minio_service()
    meta = row.process_meta or {}
    upload_id = meta.get("uploadId")
    if upload_id:
        size = await _complete_multipart(minio, row, str(upload_id))
    else:
        size = await _verify_single_put(minio, row)

    conflict = await media_repository.find_hash_conflict(
        session, row.source_id, row.file_hash, exclude_id=row.id
    )
    if conflict is not None:
        await minio.remove_files([row.cos_key])
        raise ConflictError(
            f"与既有素材「{conflict.title}」（第 {conflict.episode_no or '-'} 集）内容重复"
        )
    row.file_size = size
    if upload_id:
        row.process_meta = {
            k: v for k, v in meta.items() if k not in _SESSION_META_KEYS
        }
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


async def _verify_single_put(minio: MinIOService, row: KbMedia) -> int:
    """单 PUT 路径：HEAD 核对 size/etag(md5)，不符清除孤儿对象并抛 422。"""
    stat = await minio.stat_object(row.cos_key)
    if stat is None:
        raise UnprocessableEntityError("对象尚未上传完成或已被清理，请重新上传")
    size, etag = stat
    if etag and row.file_hash.lower() not in (etag, etag.replace("-", "")):
        await minio.remove_files([row.cos_key])
        raise UnprocessableEntityError(
            "上传内容校验失败（etag 与登记 md5 不符），已清除孤儿对象，请重试上传"
        )
    return size


async def _complete_multipart(minio: MinIOService, row: KbMedia, upload_id: str) -> int:
    """multipart 路径：服务端 list_parts 汇总核对 declaredSize 后合并。"""
    meta = row.process_meta or {}
    declared = int(meta.get("declaredSize") or 0)
    try:
        parts = await minio.list_multipart_parts(row.cos_key, upload_id)
    except MultipartSessionNotFoundError as exc:
        raise UnprocessableEntityError(
            "分片会话已失效，请重新发起上传"
        ) from exc
    total = sum(p.size for p in parts)
    if not parts or (declared and total != declared):
        raise UnprocessableEntityError(
            "分片尚未传齐（已传大小与登记不符），请续传缺失分片后重试"
        )
    await minio.complete_multipart_upload(
        row.cos_key, upload_id, sorted(parts, key=lambda p: p.part_number)
    )
    stat = await minio.stat_object(row.cos_key)
    if stat is None:
        raise UnprocessableEntityError("分片合并后对象缺失，请重新上传")
    return stat[0]


async def create_upload_session(
    session: AsyncSession,
    media_id: int,
    data: KbUploadSessionRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbUploadSessionResponse:
    """创建或续传分片上传会话。

    uploadId 真相源在 ``process_meta``：已有会话则 list_parts 返回已完成分片
    （断点续传），仅对缺失分片签发 URL；会话失效（NoSuchUpload）自动重建。
    ``resumeUploadId`` 仅作前端提示，与行内不一致时以行内为准。
    """
    row = await get_media(session, media_id)
    if row.process_status != "uploaded" or row.file_size != 0:
        raise ConflictError("素材已上传完成或不在待上传状态")
    minio = get_minio_service()

    meta = dict(row.process_meta or {})
    upload_id = meta.get("uploadId")
    completed: list[MultipartPart] = []
    if upload_id:
        try:
            completed = await minio.list_multipart_parts(row.cos_key, str(upload_id))
        except MultipartSessionNotFoundError:
            upload_id = None
            completed = []
    if upload_id is None:
        upload_id = await minio.create_multipart_upload(row.cos_key)
        meta["sessionStartedAt"] = utc_now().isoformat()
    meta.update(
        {
            "uploadId": upload_id,
            "partSize": data.part_size,
            "partCount": data.part_count,
        }
    )
    row.process_meta = meta
    await session.commit()

    done_numbers = {p.part_number for p in completed}
    ttl = timedelta(seconds=get_settings().kb_part_presign_ttl_seconds)
    part_urls: list[KbUploadSessionPartUrl] = []
    for number in range(1, data.part_count + 1):
        if number in done_numbers:
            continue
        url = await minio.presigned_part_url(row.cos_key, upload_id, number, ttl)
        part_urls.append(KbUploadSessionPartUrl(part_number=number, url=url))

    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_MEDIA_SESSION,
        detail={
            "mediaId": row.id,
            "uploadId": upload_id,
            "resumed": bool(done_numbers),
            "completedParts": len(done_numbers),
        },
        ip=ip,
    )
    logger.info(
        "kb_media_upload_session",
        media_id=row.id,
        upload_id=upload_id,
        completed=len(done_numbers),
        total=data.part_count,
    )
    return KbUploadSessionResponse(
        media_id=row.id,
        upload_id=upload_id,
        part_size=data.part_size,
        part_count=data.part_count,
        completed_parts=[
            KbUploadSessionPart(part_number=p.part_number, etag=p.etag, size=p.size)
            for p in sorted(completed, key=lambda p: p.part_number)
        ],
        part_urls=part_urls,
    )


async def abort_upload_session(
    session: AsyncSession, media_id: int, *, actor_id: int, ip: str | None = None
) -> None:
    """放弃分片会话：abort 释放已传分片存储并清 process_meta 会话键（幂等）。"""
    row = await get_media(session, media_id)
    meta = dict(row.process_meta or {})
    upload_id = meta.get("uploadId")
    if not upload_id:
        return
    await get_minio_service().abort_multipart_upload(row.cos_key, str(upload_id))
    row.process_meta = {k: v for k, v in meta.items() if k not in _SESSION_META_KEYS}
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_MEDIA_SESSION,
        detail={"mediaId": row.id, "aborted": True},
        ip=ip,
    )
    await session.commit()
    logger.info("kb_media_upload_session_aborted", media_id=row.id)


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


async def requeue_failed_media(
    session: AsyncSession, media_id: int, *, actor_id: int, ip: str | None = None
) -> KbMediaResponse:
    """失败素材重新入队（failed → queued）：已成功分片有 COS 缓存，重跑只补缺失分片。"""
    row = await get_media(session, media_id)
    if row.process_status != KbProcessStatus.FAILED:
        raise ConflictError(f"仅失败素材可重新转写，当前状态：{row.process_status}")
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
