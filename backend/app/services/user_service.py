"""User business services."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import RegisterRequest


async def has_users(session: AsyncSession) -> bool:
    """Check whether at least one user already exists."""
    result = await session.execute(select(func.count(User.id)))
    return result.scalar_one() > 0


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """通过用户名查询用户。"""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """通过邮箱查询用户。"""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, data: RegisterRequest) -> User:
    """创建新用户。

    The very first registered account is granted the ``admin`` role so that
    there is always an administrator who can access the management console.
    """
    is_first_user = not await has_users(session)
    user = User(
        username=data.username,
        email=data.email,
        password_hash=get_password_hash(data.password),
        role="admin" if is_first_user else "user",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    """验证用户名和密码。"""
    user = await get_user_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


async def update_last_login(session: AsyncSession, user: User) -> None:
    """更新最后登录时间。"""
    user.last_login_at = datetime.utcnow()
    await session.commit()
