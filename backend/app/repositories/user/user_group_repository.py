"""用户组仓储。"""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_group import UserGroup
from app.repositories.base import BaseRepository


class UserGroupRepository(BaseRepository[UserGroup]):
    """用户组的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserGroup)

    async def get_by_name(self, name: str) -> UserGroup | None:
        """按组名获取用户组。"""
        result = await self.execute(select(UserGroup).where(UserGroup.name == name))
        return cast(UserGroup | None, result.scalar_one_or_none())

    async def exists_by_name(self, name: str) -> bool:
        """判断指定组名是否存在。"""
        result = await self.execute(
            select(UserGroup.id).where(UserGroup.name == name).limit(1)
        )
        return result.scalar_one_or_none() is not None
