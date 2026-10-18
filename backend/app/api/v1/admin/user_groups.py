"""管理后台用户组 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.user_group import (
    FeatureCatalogItem,
    UserGroupCreate,
    UserGroupResponse,
    UserGroupUpdate,
)
from app.services.admin.user_groups import AdminUserGroupService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=list[UserGroupResponse])
async def list_groups(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserGroupResponse]:
    """全部用户组（不分页）。"""
    groups = await AdminUserGroupService(session).list_groups()
    return [UserGroupResponse.model_validate(group) for group in groups]


@router.get("/features", response_model=list[FeatureCatalogItem])
async def list_features(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[FeatureCatalogItem]:
    """功能模块目录（供组编辑表单渲染开关清单）。"""
    return await AdminUserGroupService.list_features()


@router.post(
    "/", response_model=UserGroupResponse, status_code=status.HTTP_201_CREATED
)
async def create_group(
    data: UserGroupCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserGroupResponse:
    """创建用户组。"""
    group = await AdminUserGroupService(session).create_group(data)
    return UserGroupResponse.model_validate(group)


@router.put("/{group_id}", response_model=UserGroupResponse)
async def update_group(
    group_id: int,
    data: UserGroupUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserGroupResponse:
    """更新用户组（仅声明字段生效）。"""
    group = await AdminUserGroupService(session).update_group(group_id, data)
    return UserGroupResponse.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除用户组（组内仍有成员时拒绝）。"""
    await AdminUserGroupService(session).delete_group(group_id)
