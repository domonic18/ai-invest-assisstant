"""用户仓储。"""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """用户的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        """按用户名获取用户。"""
        result = await self.execute(select(User).where(User.username == username))
        return cast(User | None, result.scalar_one_or_none())

    async def get_by_email(self, email: str) -> User | None:
        """按邮箱获取用户。"""
        result = await self.execute(select(User).where(User.email == email))
        return cast(User | None, result.scalar_one_or_none())

    async def exists_by_username(self, username: str) -> bool:
        """判断指定用户名的用户是否存在。"""
        result = await self.execute(
            select(User.id).where(User.username == username).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_by_email(self, email: str) -> bool:
        """判断指定邮箱的用户是否存在。"""
        result = await self.execute(
            select(User.id).where(User.email == email).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def count(self) -> int:
        """返回用户总数。"""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(User)
        return (await self.scalar(stmt)) or 0
