"""Admin user management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.stock import PaginatedResponse
from app.schemas.user import (
    AdminUserCreate,
    AdminUserResetPassword,
    AdminUserUpdate,
    UserResponse,
)
from app.services.admin.users import AdminUserService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """查询用户列表。"""
    items, total = await AdminUserService(session).list_users(page, page_size)
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[UserResponse.model_validate(item) for item in items],
    )


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: AdminUserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """创建用户。"""
    try:
        user = await AdminUserService(session).create_user(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """获取单个用户信息。"""
    user = await AdminUserService(session).get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """更新用户信息。"""
    try:
        user = await AdminUserService(session).update_user(user_id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除用户。"""
    try:
        await AdminUserService(session).delete_user(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_user_password(
    user_id: int,
    data: AdminUserResetPassword,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """重置用户密码。"""
    user = await AdminUserService(session).reset_password(user_id, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)
