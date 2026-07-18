"""User repository."""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Data access for users."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        """Fetch a user by username."""
        result = await self.execute(select(User).where(User.username == username))
        return cast(User | None, result.scalar_one_or_none())

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by email."""
        result = await self.execute(select(User).where(User.email == email))
        return cast(User | None, result.scalar_one_or_none())

    async def exists_by_username(self, username: str) -> bool:
        """Return True if a user with the given username exists."""
        result = await self.execute(
            select(User.id).where(User.username == username).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_by_email(self, email: str) -> bool:
        """Return True if a user with the given email exists."""
        result = await self.execute(
            select(User.id).where(User.email == email).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def count(self) -> int:
        """Return the total number of users."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(User)
        return (await self.scalar(stmt)) or 0
