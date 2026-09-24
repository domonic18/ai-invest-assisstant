"""管理后台社媒追踪 API（账号 CRUD / 采集健康 / ASR 渠道配置）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.core.exceptions import NotFoundError
from app.dependencies import client_ip, get_current_admin_user, get_db
from app.models.user import User
from app.repositories.social import account_repository, post_repository
from app.schemas.social import (
    AsrConfigResponse,
    AsrConfigTestResponse,
    AsrConfigUpdateRequest,
    CookieImportRequest,
    CookieImportResponse,
    SocialAccountAdminResponse,
    SocialAccountCreateRequest,
    SocialAccountsAdminResponse,
    SocialAccountUpdateRequest,
    SocialBackfillResponse,
    SocialPostDebugResponse,
    SocialPostsDebugResponse,
    SocialStatusResponse,
)
from app.services.social import (
    account_service,
    asr_config_service,
    collection_service,
)

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/accounts", response_model=SocialAccountsAdminResponse)
async def list_accounts(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> SocialAccountsAdminResponse:
    """追踪账号分页清单（含诊断列）。"""
    accounts, total = await account_repository.list_accounts_paged(
        session, page=page, page_size=page_size
    )
    return SocialAccountsAdminResponse(
        items=[SocialAccountAdminResponse.model_validate(a) for a in accounts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/accounts",
    response_model=SocialAccountAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    payload: SocialAccountCreateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> SocialAccountAdminResponse:
    """登记追踪账号（sec_uid 支持裸 ID/主页链接/分享短链）。"""
    account = await account_service.create_account(
        session,
        platform=payload.platform,
        sec_uid_or_url=payload.sec_uid_or_url,
        alias=payload.alias,
        category=payload.category,
        poll_interval_minutes=payload.poll_interval_minutes or 60,
        remark=payload.remark,
        actor_id=admin.id,
        ip=client_ip(request),
    )
    return SocialAccountAdminResponse.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=SocialAccountAdminResponse)
async def update_account(
    account_id: int,
    payload: SocialAccountUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> SocialAccountAdminResponse:
    """更新追踪账号（仅更新传入项，启停走 is_active）。"""
    account = await account_service.update_account(
        session,
        account_id,
        actor_id=admin.id,
        ip=client_ip(request),
        **payload.model_dump(exclude_unset=True),
    )
    return SocialAccountAdminResponse.model_validate(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """删除追踪账号（post 级联删除，判断历史随删）。"""
    await account_service.delete_account(
        session,
        account_id,
        actor_id=admin.id,
        ip=client_ip(request),
    )


@router.post("/accounts/{account_id}/backfill", response_model=SocialBackfillResponse)
async def backfill_account(
    account_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> SocialBackfillResponse:
    """触发账号历史视频回填采集（忽略增量地板深拉，幂等可重跑）。"""
    log = await account_service.trigger_backfill(
        session,
        account_id,
        actor_id=admin.id,
        ip=client_ip(request),
    )
    return SocialBackfillResponse(log_id=log.id, celery_task_id=log.celery_task_id)


@router.get("/accounts/{account_id}/posts", response_model=SocialPostsDebugResponse)
async def list_account_posts(
    account_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(30, ge=1, le=100),
) -> SocialPostsDebugResponse:
    """账号最近作品排查清单（转写状态/降级原因/判级结果，未判也在列）。"""
    if await account_repository.get(session, account_id) is None:
        raise NotFoundError("追踪账号不存在")
    items = await post_repository.list_admin_posts(session, account_id, limit=limit)
    return SocialPostsDebugResponse(
        items=[SocialPostDebugResponse.model_validate(item) for item in items]
    )


@router.post("/cookies", response_model=CookieImportResponse)
async def import_cookie(
    payload: CookieImportRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> CookieImportResponse:
    """手动导入抖音 Cookie（ttwid 必需，合并入 jar 池，写审计）。"""
    jars = await collection_service.import_cookie(
        session,
        payload.cookie,
        actor_id=admin.id,
        ip=client_ip(request),
    )
    return CookieImportResponse(cookie_jars_available=jars)


@router.get("/status", response_model=SocialStatusResponse)
async def get_status(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SocialStatusResponse:
    """采集健康聚合（抖音 Cookie 池 + 今日采集量 + ASR 记账）。"""
    return await collection_service.get_status_aggregate(session)


@router.get("/asr-config", response_model=AsrConfigResponse)
async def get_asr_config(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AsrConfigResponse:
    """ASR 配置 masked 视图（密钥只回脱敏串）。"""
    config = await asr_config_service.get_or_create_config(session)
    return asr_config_service.to_response(config)


@router.put("/asr-config", response_model=AsrConfigResponse)
async def update_asr_config(
    payload: AsrConfigUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> AsrConfigResponse:
    """更新 ASR 配置（apiKey write-only：留空不换，写审计）。"""
    return await asr_config_service.update_config(session, payload, actor_id=admin.id)


@router.post("/asr-config/test", response_model=AsrConfigTestResponse)
async def test_asr_config(
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> AsrConfigTestResponse:
    """连接测试：内置样例音频实调转写接口（不抛异常，失败给原因）。"""
    return await asr_config_service.test_connection(session, actor_id=admin.id)
