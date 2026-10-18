"""后台用户组业务服务。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.features import FEATURE_KEYS, FEATURE_LABELS
from app.core.exceptions import ConflictError, NotFoundError
from app.models.user import User
from app.models.user_group import UserGroup
from app.repositories.user.user_group_repository import UserGroupRepository
from app.schemas.user_group import (
    FeatureCatalogItem,
    UserGroupCreate,
    UserGroupUpdate,
)


class AdminUserGroupService:
    """后台用户组管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserGroupRepository(session)

    async def list_groups(self) -> list[UserGroup]:
        """全部用户组（不分页，量级为个位数）。"""
        return await self.repo.get_all(order_by=UserGroup.id)

    @staticmethod
    async def list_features() -> list[FeatureCatalogItem]:
        """功能模块目录（key + 展示名）。"""
        return [
            FeatureCatalogItem(key=key, label=FEATURE_LABELS.get(key, key))
            for key in FEATURE_KEYS
        ]

    async def create_group(self, data: UserGroupCreate) -> UserGroup:
        """创建用户组，组名重复时抛 ConflictError。"""
        if await self.repo.exists_by_name(data.name):
            raise ConflictError(f"用户组「{data.name}」已存在")
        group = UserGroup(
            name=data.name,
            description=data.description,
            permissions=list(data.permissions),
        )
        self.repo.add(group)
        await self.session.commit()
        await self.repo.refresh(group)
        return group

    async def update_group(self, group_id: int, data: UserGroupUpdate) -> UserGroup:
        """更新用户组（仅声明字段生效），重名抛 ConflictError。"""
        group = await self._get_or_raise(group_id)
        if data.name is not None and data.name != group.name:
            if await self.repo.exists_by_name(data.name):
                raise ConflictError(f"用户组「{data.name}」已存在")
            group.name = data.name
        if data.description is not None:
            group.description = data.description
        if data.permissions is not None:
            group.permissions = list(data.permissions)
        if data.is_active is not None:
            group.is_active = data.is_active
        await self.session.commit()
        await self.repo.refresh(group)
        return group

    async def delete_group(self, group_id: int) -> None:
        """删除用户组；组内仍有成员时抛 ConflictError。"""
        group = await self._get_or_raise(group_id)
        member_count = (
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.group_id == group_id)
            )
        ) or 0
        if member_count:
            raise ConflictError(f"用户组仍有 {member_count} 个成员，请先移出后再删除")
        await self.repo.delete(group)
        await self.session.commit()

    async def _get_or_raise(self, group_id: int) -> UserGroup:
        group = await self.repo.get(group_id)
        if group is None:
            raise NotFoundError(f"User group {group_id} not found")
        return group
