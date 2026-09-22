"""素材上传链路：批量登记 + 预签名直传、回调核验与字节入账。

1. ``init_uploads`` 批量建行（course 按序自动编号）+ 预签名 PUT，浏览器直传 COS；
2. ``confirm_uploaded`` 服务端 HEAD 核对 size/etag(md5) → 同库同哈希 409 →
   核验通过记 ``file_size`` 并累加 ``storage_bytes``。

预签名 URL 使用公网 endpoint 签名（minio_service 内部处理），有效期 6 小时。
"""

from datetime import timedelta
from pathlib import PurePosixPath

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbProcessStatus
from app.core.exceptions import ConflictError, UnprocessableEntityError
from app.models.kb import KbMedia
from app.repositories.kb import media_repository, source_repository
from app.schemas.kb import (
    KbMediaInitRequest,
    KbMediaInitResponse,
    KbMediaInitResult,
    KbMediaResponse,
)
from app.services.admin.audit_service import record_audit
from app.services.common.minio_service import (
    MinIOService,
    MultipartSessionNotFoundError,
    get_minio_service,
)
from app.services.kb.media_service import (
    _cos_key,
    _display_file_name,
    _sanitize_file_name,
    get_media,
    to_view,
)
from app.services.kb.media_upload_session import _SESSION_META_KEYS
from app.services.kb.source_service import get_source

logger = structlog.get_logger(__name__)

_PRESIGN_TTL_SECONDS = 6 * 3600

AUDIT_MEDIA_INIT = "kb.media.init"
AUDIT_MEDIA_UPLOADED = "kb.media.uploaded"


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
        and m.process_status == KbProcessStatus.UPLOADED
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
