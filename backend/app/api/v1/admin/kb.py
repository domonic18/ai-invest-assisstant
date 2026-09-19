"""管理后台知识库 API 端点（F-KB：知识源 CRUD + 素材上传链路）。

上传链路（arch/12 §3）：init 批量建行 + 预签名 PUT → 浏览器直传 COS →
uploaded 回调服务端核对。所有变更动作入审计（audit_log）。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.dependencies import get_current_admin_user, get_db
from app.models.user import User
from app.schemas.kb import (
    KbChaptersPublishRequest,
    KbChaptersResponse,
    KbConfirmCostRequest,
    KbConfirmCostResponse,
    KbCostEstimateRequest,
    KbCostEstimateResponse,
    KbKnowledgePointResponse,
    KbMediaInitRequest,
    KbMediaInitResponse,
    KbMediaPatchRequest,
    KbMediaResponse,
    KbPointCreateRequest,
    KbPointListResponse,
    KbPointPatchRequest,
    KbPointRejectRequest,
    KbPointsMergeRequest,
    KbSourceCreateRequest,
    KbSourceResponse,
    KbSourceUpdateRequest,
    KbTranscriptResponse,
    KbTranscriptSaveResponse,
    KbTranscriptUpdateRequest,
    KbUploadSessionRequest,
    KbUploadSessionResponse,
)
from app.services.kb import (
    cost_service,
    media_service,
    review_service,
    source_service,
    transcript_service,
)

router = APIRouter(prefix="/kb", dependencies=[Depends(get_current_admin_user)])


def _client_ip(request: Request) -> str | None:
    """取客户端 IP（代理场景取 X-Forwarded-For 首个）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/sources", response_model=list[KbSourceResponse])
async def list_sources(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[KbSourceResponse]:
    """知识库列表（隐藏软删行）。"""
    return await source_service.list_sources(session)


@router.post("/sources", response_model=KbSourceResponse, status_code=201)
async def create_source(
    data: KbSourceCreateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbSourceResponse:
    """新建知识库。"""
    return await source_service.create_source(
        session, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.patch("/sources/{source_id}", response_model=KbSourceResponse)
async def update_source(
    source_id: int,
    data: KbSourceUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbSourceResponse:
    """编辑知识库基础信息。"""
    return await source_service.update_source(
        session, source_id, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """软删知识库（24h 恢复窗）。"""
    await source_service.soft_delete_source(
        session, source_id, actor_id=admin.id, ip=_client_ip(request)
    )


@router.post("/sources/{source_id}/restore", response_model=KbSourceResponse)
async def restore_source(
    source_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbSourceResponse:
    """恢复窗内撤销软删。"""
    return await source_service.restore_source(
        session, source_id, actor_id=admin.id, ip=_client_ip(request)
    )


@router.get("/sources/{source_id}/media", response_model=list[KbMediaResponse])
async def list_media(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[KbMediaResponse]:
    """素材列表（附带知识点数与待索引分段数）。"""
    return await media_service.list_media(session, source_id)


@router.post("/sources/{source_id}/media/init", response_model=KbMediaInitResponse)
async def init_uploads(
    source_id: int,
    data: KbMediaInitRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbMediaInitResponse:
    """批量建行 + 预签名 PUT（浏览器直传 COS）。"""
    return await media_service.init_uploads(
        session, source_id, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.post("/cost-estimate", response_model=KbCostEstimateResponse)
async def cost_estimate(
    data: KbCostEstimateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbCostEstimateResponse:
    """分项预估建库费用（uploaded 素材推进到 awaiting_cost）。"""
    return await cost_service.estimate_cost(
        session, data.source_id, data.media_ids
    )


@router.post(
    "/sources/{source_id}/confirm-cost", response_model=KbConfirmCostResponse
)
async def confirm_cost(
    source_id: int,
    data: KbConfirmCostRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbConfirmCostResponse:
    """确认费用入队（awaiting_cost → queued，审计 kb.cost.confirm）。"""
    queued = await cost_service.confirm_cost(
        session, source_id, data.media_ids, actor_id=admin.id, ip=_client_ip(request)
    )
    return KbConfirmCostResponse(queued_ids=queued)


@router.post("/media/{media_id}/upload-session", response_model=KbUploadSessionResponse)
async def create_upload_session(
    media_id: int,
    data: KbUploadSessionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbUploadSessionResponse:
    """创建/续传分片上传会话（已传分片服务端真相，仅缺失分片签 URL）。"""
    return await media_service.create_upload_session(
        session, media_id, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.delete("/media/{media_id}/upload-session", status_code=204)
async def abort_upload_session(
    media_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """放弃分片会话（释放已传分片存储，幂等）。"""
    await media_service.abort_upload_session(
        session, media_id, actor_id=admin.id, ip=_client_ip(request)
    )


@router.post("/media/{media_id}/uploaded", response_model=KbMediaResponse)
async def confirm_uploaded(
    media_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbMediaResponse:
    """上传完成回调：分片合并或 HEAD 核对 + 哈希去重 + 字节入账。"""
    return await media_service.confirm_uploaded(
        session, media_id, actor_id=admin.id, ip=_client_ip(request)
    )


@router.patch("/media/{media_id}", response_model=KbMediaResponse)
async def patch_media(
    media_id: int,
    data: KbMediaPatchRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbMediaResponse:
    """修正集号/标题/时长/页数。"""
    return await media_service.patch_media(
        session, media_id, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.post("/media/{media_id}/requeue", response_model=KbMediaResponse)
async def requeue_media(
    media_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbMediaResponse:
    """失败素材重新入队（failed → queued），转写下轮扫描拾起。"""
    return await media_service.requeue_failed_media(
        session, media_id, actor_id=admin.id, ip=_client_ip(request)
    )


@router.delete("/media/{media_id}", status_code=204)
async def delete_media(
    media_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """单集软删（24h 恢复窗）。"""
    await media_service.soft_delete_media(
        session, media_id, actor_id=admin.id, ip=_client_ip(request)
    )


@router.post("/media/{media_id}/restore", response_model=KbMediaResponse)
async def restore_media(
    media_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbMediaResponse:
    """恢复窗内撤销单集软删。"""
    return await media_service.restore_media(
        session, media_id, actor_id=admin.id, ip=_client_ip(request)
    )


@router.get(
    "/sources/{source_id}/transcript/{media_id}",
    response_model=KbTranscriptResponse,
)
async def get_transcript(
    source_id: int,
    media_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbTranscriptResponse:
    """单集文稿读取（分段按 seqNo 升序）。"""
    return await transcript_service.get_transcript(session, source_id, media_id)


@router.put(
    "/sources/{source_id}/transcript/{media_id}",
    response_model=KbTranscriptSaveResponse,
)
async def save_transcript(
    source_id: int,
    media_id: int,
    data: KbTranscriptUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbTranscriptSaveResponse:
    """文稿批量保存：变化分段置脏 + edited_at（审计 kb.transcript.save）。"""
    return await transcript_service.save_transcript(
        session,
        source_id,
        media_id,
        data,
        actor_id=admin.id,
        ip=_client_ip(request),
    )


# ---------------------------------------------------------------------------
# 知识审核（F-KB-03：章节树 + 知识点工作台）
# ---------------------------------------------------------------------------


@router.get("/sources/{source_id}/chapters", response_model=KbChaptersResponse)
async def get_chapters(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbChaptersResponse:
    """知识源目录树（draft 供编辑，published 为生效版本）。"""
    return await review_service.get_chapters(session, source_id)


@router.post(
    "/sources/{source_id}/chapters/publish", response_model=KbChaptersResponse
)
async def publish_chapters(
    source_id: int,
    data: KbChaptersPublishRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbChaptersResponse:
    """整棵发布目录树（审计 kb.chapters.publish）。"""
    return await review_service.publish_chapters(
        session, source_id, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.get("/sources/{source_id}/points", response_model=KbPointListResponse)
async def list_points(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    status: Literal["draft", "published", "rejected"] | None = Query(default=None),
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> KbPointListResponse:
    """知识点分页列表 + 状态计数（审核工作台首屏）。"""
    return await review_service.list_points(
        session, source_id, status=status, page=page, page_size=page_size
    )


@router.post("/points/merge", response_model=KbKnowledgePointResponse)
async def merge_points(
    data: KbPointsMergeRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbKnowledgePointResponse:
    """重复草稿合并（related 并集进目标，源行硬删；审计 kb.point.merge）。"""
    return await review_service.merge_points(
        session, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.post("/points", response_model=KbKnowledgePointResponse, status_code=201)
async def create_point(
    data: KbPointCreateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbKnowledgePointResponse:
    """人工新增知识卡片（status=draft 走同一审核流；审计 kb.point.create）。"""
    return await review_service.create_point(
        session, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.patch("/points/{point_id}", response_model=KbKnowledgePointResponse)
async def patch_point(
    point_id: int,
    data: KbPointPatchRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbKnowledgePointResponse:
    """白名单修订（excerpt/时间码定位字段不可改，422；审计 kb.point.patch）。"""
    return await review_service.patch_point(
        session, point_id, data, actor_id=admin.id, ip=_client_ip(request)
    )


@router.post("/points/{point_id}/approve", response_model=KbKnowledgePointResponse)
async def approve_point(
    point_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbKnowledgePointResponse:
    """通过发布（→ published 并置 embedding_dirty；审计 kb.point.approve）。"""
    return await review_service.approve_point(
        session, point_id, actor_id=admin.id, ip=_client_ip(request)
    )


@router.post("/points/{point_id}/reject", response_model=KbKnowledgePointResponse)
async def reject_point(
    point_id: int,
    data: KbPointRejectRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbKnowledgePointResponse:
    """驳回（理由入 review_note；原 published 置脏；审计 kb.point.reject）。"""
    return await review_service.reject_point(
        session, point_id, data, actor_id=admin.id, ip=_client_ip(request)
    )
