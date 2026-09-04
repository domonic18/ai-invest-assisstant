"""后台用户业务服务。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user.user_repository import UserRepository
from app.schemas.user import AdminUserCreate, AdminUserUpdate


class AdminUserService:
    """后台用户管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def list_users(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[User], int]:
        """分页查询用户列表。"""
        offset = (page - 1) * page_size
        items = await self.repo.get_all(
            order_by=User.id,
            offset=offset,
            limit=page_size,
        )
        total = await self.repo.count()
        return items, total

    async def get_user(self, user_id: int) -> User | None:
        """按 ID 查询用户。"""
        return await self.repo.get(user_id)

    async def create_user(self, data: AdminUserCreate) -> User:
        """创建新用户。"""
        if await self.repo.exists_by_username(data.username):
            raise ValueError(f"Username {data.username} already exists")
        if await self.repo.exists_by_email(data.email):
            raise ValueError(f"Email {data.email} already exists")

        user = User(
            username=data.username,
            email=data.email,
            password_hash=get_password_hash(data.password),
            role=data.role,
            is_active=data.is_active,
        )
        self.repo.add(user)
        await self.session.commit()
        await self.repo.refresh(user)
        return user

    async def update_user(self, user_id: int, data: AdminUserUpdate) -> User | None:
        """更新用户信息。"""
        user = await self.repo.get(user_id)
        if not user:
            return None

        if data.username is not None and data.username != user.username:
            if await self.repo.exists_by_username(data.username):
                raise ValueError(f"Username {data.username} already exists")
            user.username = data.username
        if data.email is not None and data.email != user.email:
            if await self.repo.exists_by_email(data.email):
                raise ValueError(f"Email {data.email} already exists")
            user.email = data.email
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active

        await self.session.commit()
        await self.repo.refresh(user)
        return user

    async def delete_user(self, user_id: int) -> None:
        """删除用户。"""
        user = await self.repo.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        await self.repo.delete(user)
        await self.session.commit()

    async def reset_password(self, user_id: int, password: str) -> User | None:
        """重置用户密码。"""
        user = await self.repo.get(user_id)
        if not user:
            return None
        user.password_hash = get_password_hash(password)
        await self.session.commit()
        await self.repo.refresh(user)
        return user

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
