"""课程视频关键帧：管理面（图片资产列表/重新描述/索引排除开关）。

管线本体见 ``vision_extract``（选帧）与 ``vision_describe``（VLM 描述）；
本模块是管理端对 ``kb_image_asset`` 的可见性与人工干预入口。
"""

from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbDescribeStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.models.kb import KbImageAsset, KbMedia
from app.schemas.kb import KbImageAssetResponse, KbImageListResponse
from app.services.admin.audit_service import record_audit
from app.services.common.minio_service import get_minio_service
from app.services.kb.source_service import get_source
from app.services.kb.vision_common import (
    _THUMB_URL_TTL,
    AUDIT_IMAGE_EXCLUDE,
    AUDIT_IMAGE_REDESCRIBE,
)

logger = structlog.get_logger(__name__)


async def list_images(
    session: AsyncSession,
    source_id: int,
    *,
    media_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> KbImageListResponse:
    """图片资产分页列表（书嵌图 + 课程关键帧，缩略图短时效签名）。"""
    await get_source(session, source_id)
    conditions = [KbImageAsset.source_id == source_id]
    if media_id is not None:
        conditions.append(KbImageAsset.media_id == media_id)
    if status is not None:
        conditions.append(KbImageAsset.describe_status == status)
    total = (
        await session.execute(
            select(func.count()).select_from(KbImageAsset).where(*conditions)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(KbImageAsset)
                .where(*conditions)
                .order_by(KbImageAsset.media_id, KbImageAsset.start_ms, KbImageAsset.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    minio = get_minio_service()
    items = [
        await _image_response(minio, row)
        for row in rows
    ]
    return KbImageListResponse(items=items, total=total)


async def _image_response(
    minio: Any, row: KbImageAsset
) -> KbImageAssetResponse:
    return KbImageAssetResponse(
        id=row.id,
        source_id=row.source_id,
        media_id=row.media_id,
        page_no=row.page_no,
        start_ms=row.start_ms,
        end_ms=row.end_ms,
        thumb_url=await minio.get_presigned_url(
            row.thumb_cos_key or row.cos_key, expires=_THUMB_URL_TTL
        ),
        describe_status=row.describe_status,
        describe_attempts=row.describe_attempts,
        text_in_image=row.text_in_image,
        caption=row.caption,
        vision_description=row.vision_description,
        index_excluded=row.index_excluded,
        created_at=row.created_at,
    )


async def redescribe_image(
    session: AsyncSession,
    image_id: int,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbImageAssetResponse:
    """重新描述：置回 pending 重跑（清旧文本，下一轮 kb-vision 拾起）。"""
    row = await session.get(KbImageAsset, image_id)
    if row is None:
        raise NotFoundError("图片资产不存在")
    media = await session.get(KbMedia, row.media_id)
    if media is None or media.deleted_at is not None:
        raise ConflictError("所属素材已删除，无法重新描述")
    if media.media_kind != "video":
        raise ConflictError("仅课程视频关键帧支持重新描述")
    row.describe_status = KbDescribeStatus.PENDING
    row.describe_attempts = 0
    row.text_in_image = None
    row.caption = None
    row.vision_description = None
    row.embedding_dirty = True
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_IMAGE_REDESCRIBE,
        detail={"imageId": image_id, "mediaId": row.media_id},
        ip=ip,
    )
    await session.commit()
    return await _image_response(get_minio_service(), row)


async def set_image_excluded(
    session: AsyncSession,
    image_id: int,
    excluded: bool,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbImageAssetResponse:
    """索引排除开关：排除置脏（批次 E 检索索引构建时过滤并清理）。"""
    row = await session.get(KbImageAsset, image_id)
    if row is None:
        raise NotFoundError("图片资产不存在")
    if row.index_excluded != excluded:
        row.index_excluded = excluded
        row.embedding_dirty = True
        await record_audit(
            session,
            actor_id=actor_id,
            action=AUDIT_IMAGE_EXCLUDE,
            detail={"imageId": image_id, "excluded": excluded},
            ip=ip,
        )
        await session.commit()
    return await _image_response(get_minio_service(), row)
