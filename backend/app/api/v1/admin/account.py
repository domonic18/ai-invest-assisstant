"""管理端账号治理：全站用量看板与全局设置（arch/10 §7）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.models.user import User
from app.schemas.account import (
    AccountSettingsResponse,
    AccountSettingsUpdateRequest,
    UsageDashboardResponse,
    UsagePerUserResponse,
)
from app.services.admin.approval_service import ApprovalService
from app.services.quota import account_settings
from app.services.quota.constants import (
    SETTING_ADMIN_EXEMPT,
    SETTING_DEFAULT_QUOTA_TOKENS,
    SETTING_PENDING_EXPIRE_DAYS,
)
from app.services.quota.usage_query_service import (
    dashboard as usage_dashboard,
)
from app.services.quota.usage_query_service import (
    per_user_usage,
)

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/usage/dashboard", response_model=UsageDashboardResponse)
async def get_usage_dashboard(
    session: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
) -> UsageDashboardResponse:
    """全站 token 用量看板（北京时间日分桶；趋势/Top 用户/功能与模型分布/estimated 占比/耗尽数）。"""
    days = max(1, min(days, 365))
    data = await usage_dashboard(session, days=days)
    return UsageDashboardResponse.model_validate(data)


@router.get("/usage/users", response_model=list[UsagePerUserResponse])
async def get_usage_per_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
) -> list[UsagePerUserResponse]:
    """按成员聚合的 token 消耗明细（总量/调用次数/最近使用/日趋势，降序）。"""
    days = max(1, min(days, 365))
    rows = await per_user_usage(session, days=days)
    return [UsagePerUserResponse.model_validate(row) for row in rows]


@router.get("/settings/account", response_model=AccountSettingsResponse)
async def get_account_settings(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AccountSettingsResponse:
    """读取账号治理全局设置。"""
    values = await account_settings.list_settings(session)
    return AccountSettingsResponse(
        default_quota_tokens=int(values[SETTING_DEFAULT_QUOTA_TOKENS]),
        pending_expire_days=int(values[SETTING_PENDING_EXPIRE_DAYS]),
        admin_exempt=bool(values[SETTING_ADMIN_EXEMPT]),
    )


@router.put("/settings/account", response_model=AccountSettingsResponse)
async def update_account_settings(
    data: AccountSettingsUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> AccountSettingsResponse:
    """更新全局设置（入审计；豁免开关变更后失效全部配额镜像）。"""
    updates: dict[str, object] = {}
    if data.default_quota_tokens is not None:
        updates[SETTING_DEFAULT_QUOTA_TOKENS] = data.default_quota_tokens
    if data.pending_expire_days is not None:
        updates[SETTING_PENDING_EXPIRE_DAYS] = data.pending_expire_days
    if data.admin_exempt is not None:
        updates[SETTING_ADMIN_EXEMPT] = data.admin_exempt
    await ApprovalService(session).apply_settings(
        admin, updates, ip=request.client.host if request.client else None
    )
    return await get_account_settings(session=session)
