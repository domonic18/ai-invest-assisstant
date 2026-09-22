"""管理后台用户管理 API 端点（含注册审批与配额治理，arch/10）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.dependencies import client_ip, get_current_admin_user, get_db
from app.models.user import User
from app.schemas.account import (
    AdminUserRowResponse,
    ApproveRequest,
    PendingApplicationResponse,
    QuotaAdjustRequest,
    QuotaResponseAdmin,
    RejectRequest,
)
from app.schemas.stock import PaginatedResponse
from app.schemas.user import (
    AdminUserCreate,
    AdminUserResetPassword,
    AdminUserUpdate,
    UserResponse,
)
from app.services.admin.approval_service import ApprovalService
from app.services.admin.users import AdminUserService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
    status: str | None = Query(None, pattern="^(pending|approved|rejected)$"),
) -> PaginatedResponse:
    """查询用户列表（含账号状态/剩余配额/累计消耗/BYOK 扩展列，可按状态过滤）。"""
    service = AdminUserService(session)
    items, total = await service.list_users(page, page_size, status=status)
    rows = await service.enrich_rows(items)
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AdminUserRowResponse.model_validate(row) for row in rows],
    )


@router.get("/pending", response_model=list[PendingApplicationResponse])
async def list_pending_applications(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PendingApplicationResponse]:
    """待审申请队列（含惰性过期清理）。"""
    rows = await ApprovalService(session).list_pending()
    return [PendingApplicationResponse.model_validate(row) for row in rows]


@router.get("/pending-count", response_model=int)
async def pending_count(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> int:
    """待审申请数（后台角标）。"""
    return await ApprovalService(session).pending_count()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: AdminUserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """创建用户。"""
    user = await AdminUserService(session).create_user(data)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """获取单个用户信息。"""
    user = await AdminUserService(session).get_user(user_id)
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """更新用户信息。"""
    user = await AdminUserService(session).update_user(user_id, data)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除用户。"""
    await AdminUserService(session).delete_user(user_id)


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_user_password(
    user_id: int,
    data: AdminUserResetPassword,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """重置用户密码。"""
    user = await AdminUserService(session).reset_password(user_id, data.password)
    return UserResponse.model_validate(user)


@router.post("/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: int,
    data: ApproveRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> UserResponse:
    """通过注册申请（可设初始配额，缺省取全局默认；动作入审计）。"""
    service = ApprovalService(session)
    await service.approve(
        admin, user_id, data.initial_quota_tokens, ip=client_ip(request)
    )
    user = await AdminUserService(session).get_user(user_id)
    return UserResponse.model_validate(user)


@router.post("/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    user_id: int,
    data: RejectRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> UserResponse:
    """驳回注册申请（原因必填，入审计；用户名/邮箱不永久占位）。"""
    service = ApprovalService(session)
    await service.reject(admin, user_id, data.reason, ip=client_ip(request))
    user = await AdminUserService(session).get_user(user_id)
    return UserResponse.model_validate(user)


@router.post("/{user_id}/quota", response_model=QuotaResponseAdmin)
async def adjust_user_quota(
    user_id: int,
    data: QuotaAdjustRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> QuotaResponseAdmin:
    """调整用户配额（adjust 追加/核减、reset 重置全局默认；入审计 + 镜像失效）。"""
    quota = await ApprovalService(session).adjust_quota(
        admin,
        user_id,
        action=data.action,
        delta_tokens=data.delta_tokens,
        ip=client_ip(request),
    )
    unlimited = quota.total_tokens is None
    return QuotaResponseAdmin(
        user_id=user_id,
        total_tokens=quota.total_tokens,
        remaining_tokens=None if unlimited else quota.total_tokens,
        unlimited=unlimited,
    )


