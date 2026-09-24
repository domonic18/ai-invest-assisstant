"""素材分片上传会话：uploadId 真相源在 process_meta，支持断点续传。

已有会话则 list_parts 返回已完成分片（仅对缺失分片签发 URL）；会话失效
（NoSuchUpload）自动重建。``resumeUploadId`` 仅作前端提示，与行内不一致时
以行内为准。
"""

from datetime import timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbProcessStatus
from app.core.clock import utc_now
from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.schemas.kb import (
    KbUploadSessionPart,
    KbUploadSessionPartUrl,
    KbUploadSessionRequest,
    KbUploadSessionResponse,
)
from app.services.admin.audit_service import record_audit
from app.services.common.minio_service import (
    MultipartPart,
    MultipartSessionNotFoundError,
    get_minio_service,
)
from app.services.kb.media_service import get_media

logger = structlog.get_logger(__name__)

# process_meta 内分片会话键（confirm 成功或 abort 后清除；declaredSize 保留作审计）
_SESSION_META_KEYS = ("uploadId", "partSize", "partCount", "sessionStartedAt")

AUDIT_MEDIA_SESSION = "kb.media.upload-session"


async def create_upload_session(
    session: AsyncSession,
    media_id: int,
    data: KbUploadSessionRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbUploadSessionResponse:
    """创建或续传分片上传会话。"""
    row = await get_media(session, media_id)
    if row.process_status != KbProcessStatus.UPLOADED or row.file_size != 0:
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
