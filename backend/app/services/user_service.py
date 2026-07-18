"""User business services."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest


class UserService:
    """User business services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def has_users(self) -> bool:
        """Check whether at least one user already exists."""
        return (await self.repo.count()) > 0

    async def get_user_by_username(self, username: str) -> User | None:
        """通过用户名查询用户。"""
        return await self.repo.get_by_username(username)

    async def get_user_by_email(self, email: str) -> User | None:
        """通过邮箱查询用户。"""
        return await self.repo.get_by_email(email)

    async def create_user(self, data: RegisterRequest) -> User:
        """创建新用户。

        The very first registered account is granted the ``admin`` role so that
        there is always an administrator who can access the management console.
        """
        is_first_user = not await self.has_users()
        user = User(
            username=data.username,
            email=data.email,
            password_hash=get_password_hash(data.password),
            role="admin" if is_first_user else "user",
        )
        self.repo.add(user)
        await self.session.commit()
        await self.repo.refresh(user)
        return user

    async def authenticate_user(self, username: str, password: str) -> User | None:
        """验证用户名和密码。"""
        user = await self.get_user_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user

    async def update_last_login(self, user: User) -> None:
        """更新最后登录时间。"""
        user.last_login_at = datetime.utcnow()
        await self.session.commit()
