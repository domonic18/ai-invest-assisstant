"""管理后台社媒追踪 API（账号 CRUD / 采集健康 / ASR 渠道配置）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.core.clock import now_cn
from app.dependencies import get_current_admin_user, get_db
from app.models.account_quota import SystemSetting
from app.models.collector_log import CollectorLog
from app.models.user import User
from app.repositories.social import account_repository, post_repository
from app.schemas.social import (
    AsrConfigResponse,
    AsrConfigTestResponse,
    AsrConfigUpdateRequest,
    AsrStatusResponse,
    DouyinStatusResponse,
    SocialAccountAdminResponse,
    SocialAccountCreateRequest,
    SocialAccountsAdminResponse,
    SocialAccountUpdateRequest,
    SocialStatusResponse,
)
from app.services.social import (
    account_service,
    asr_config_service,
    collection_service,
)

router = APIRouter(dependencies=[Depends(get_current_admin_user)])

_SOCIAL_TASK_TYPE = "social-video"
_SOCIAL_SOURCE = "douyin"


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
        ip=request.client.host if request.client else None,
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
        ip=request.client.host if request.client else None,
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
        ip=request.client.host if request.client else None,
    )


@router.get("/status", response_model=SocialStatusResponse)
async def get_status(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SocialStatusResponse:
    """采集健康聚合（抖音 Cookie 池 + 今日采集量 + ASR 记账）。"""
    day_start = now_cn().replace(hour=0, minute=0, second=0, microsecond=0)

    cookie_setting = await session.get(SystemSetting, collection_service.COOKIE_SETTING_KEY)
    jars = await collection_service.load_cookie_jars(session)

    today_collected = (
        await session.execute(
            select(func.coalesce(func.sum(CollectorLog.records_count), 0)).where(
                CollectorLog.task_name == _SOCIAL_TASK_TYPE,
                CollectorLog.source == _SOCIAL_SOURCE,
                CollectorLog.status == "success",
                CollectorLog.started_at >= day_start,
            )
        )
    ).scalar_one()
    today_failed = (
        await session.execute(
            select(func.count())
            .select_from(CollectorLog)
            .where(
                CollectorLog.task_name == _SOCIAL_TASK_TYPE,
                CollectorLog.source == _SOCIAL_SOURCE,
                CollectorLog.status == "failed",
                CollectorLog.started_at >= day_start,
            )
        )
    ).scalar_one()
    latest_error = (
        await session.execute(
            select(CollectorLog.error_msg)
            .where(
                CollectorLog.task_name == _SOCIAL_TASK_TYPE,
                CollectorLog.source == _SOCIAL_SOURCE,
                CollectorLog.status == "failed",
            )
            .order_by(CollectorLog.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    transcript_counts = await post_repository.count_transcripts_since(session, day_start)

    config = await asr_config_service.get_or_create_config(session)
    return SocialStatusResponse(
        douyin=DouyinStatusResponse(
            cookie_configured=bool(jars),
            cookie_jars_available=len(jars),
            last_bootstrap_at=cookie_setting.updated_at if cookie_setting else None,
            signature_warning=bool(latest_error and "SignatureError" in str(latest_error)),
            today_collected=int(today_collected or 0),
            today_failed=int(today_failed or 0),
        ),
        asr=AsrStatusResponse(
            enabled=config.enabled,
            configured=bool(config.api_key_encrypted),
            today_transcribed=transcript_counts.get("ok", 0),
            today_degraded=transcript_counts.get("missing", 0),
        ),
    )


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
