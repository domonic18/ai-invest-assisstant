"""Admin user business services."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import AdminUserCreate, AdminUserUpdate


class AdminUserService:
    """后台用户管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_users(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[User], int]:
        """分页查询用户列表。"""
        stmt = select(User).order_by(User.id).offset((page - 1) * page_size).limit(page_size)
        count_stmt = select(func.count()).select_from(User)
        result = await self.session.execute(stmt)
        total = await self.session.scalar(count_stmt) or 0
        return list(result.scalars().all()), total

    async def create_user(self, data: AdminUserCreate) -> User:
        """创建新用户。"""
        if await self._get_user_by_username(data.username):
            raise ValueError(f"Username {data.username} already exists")
        if await self._get_user_by_email(data.email):
            raise ValueError(f"Email {data.email} already exists")

        user = User(
            username=data.username,
            email=data.email,
            password_hash=get_password_hash(data.password),
            role=data.role,
            is_active=data.is_active,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_user(self, user_id: int, data: AdminUserUpdate) -> User | None:
        """更新用户信息。"""
        user = await self.session.get(User, user_id)
        if not user:
            return None

        if data.username is not None and data.username != user.username:
            if await self._get_user_by_username(data.username):
                raise ValueError(f"Username {data.username} already exists")
            user.username = data.username
        if data.email is not None and data.email != user.email:
            if await self._get_user_by_email(data.email):
                raise ValueError(f"Email {data.email} already exists")
            user.email = data.email
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active

        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user_id: int) -> None:
        """删除用户。"""
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        await self.session.delete(user)
        await self.session.flush()

    async def reset_password(self, user_id: int, password: str) -> User | None:
        """重置用户密码。"""
        user = await self.session.get(User, user_id)
        if not user:
            return None
        user.password_hash = get_password_hash(password)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def _get_user_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    def _to_response(self, user: User) -> dict[str, Any]:
        """序列化为用户响应字典。"""
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        }
