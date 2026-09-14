"""后台用户业务服务。"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.security import get_password_hash
from app.models.account_quota import UserAiQuota, UserLlmConfig, UserTokenUsage
from app.models.user import User
from app.repositories.user.user_repository import UserRepository
from app.schemas.user import AdminUserCreate, AdminUserUpdate
from app.services.quota import account_settings
from app.services.quota.constants import OUTLET_SYSTEM


class AdminUserService:
    """后台用户管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def list_users(
        self, page: int = 1, page_size: int = 20, status: str | None = None
    ) -> tuple[list[User], int]:
        """分页查询用户列表（可按审批状态过滤）。"""
        offset = (page - 1) * page_size
        stmt = select(User).order_by(User.id)
        count_stmt = select(func.count()).select_from(User)
        if status is not None:
            stmt = stmt.where(User.status == status)
            count_stmt = count_stmt.where(User.status == status)
        items = (await self.session.execute(stmt.offset(offset).limit(page_size))).scalars().all()
        total = int((await self.session.execute(count_stmt)).scalar_one() or 0)
        return list(items), total

    async def get_user(self, user_id: int) -> User:
        """按 ID 查询用户，缺失时抛 NotFoundError。"""
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def create_user(self, data: AdminUserCreate) -> User:
        """创建新用户（后台创建即 approved，并发默认配额）。"""
        if await self.repo.exists_by_username(data.username):
            raise BadRequestError(f"Username {data.username} already exists")
        if await self.repo.exists_by_email(data.email):
            raise BadRequestError(f"Email {data.email} already exists")

        user = User(
            username=data.username,
            email=data.email,
            password_hash=get_password_hash(data.password),
            role=data.role,
            is_active=data.is_active,
            status="approved",
        )
        self.repo.add(user)
        await self.session.flush()
        default_quota = await account_settings.get_default_quota_tokens(self.session)
        self.session.add(UserAiQuota(user_id=user.id, total_tokens=default_quota))
        await self.session.commit()
        await self.repo.refresh(user)
        return user

    async def enrich_rows(self, users: list[User]) -> list[dict[str, Any]]:
        """用户列表行富化：剩余配额 / 累计消耗 / 是否 BYOK（批量查询）。"""
        ids = [u.id for u in users]
        quotas: dict[int, UserAiQuota] = {}
        used_map: dict[int, int] = {}
        byok_ids: set[int] = set()
        admin_exempt = await account_settings.get_admin_exempt(self.session)
        if ids:
            quota_rows = (
                await self.session.execute(
                    select(UserAiQuota).where(UserAiQuota.user_id.in_(ids))
                )
            ).scalars().all()
            quotas = {row.user_id: row for row in quota_rows}
            used_rows = (
                await self.session.execute(
                    select(
                        UserTokenUsage.user_id,
                        func.coalesce(func.sum(UserTokenUsage.total_tokens), 0),
                    )
                    .where(
                        UserTokenUsage.user_id.in_(ids),
                        UserTokenUsage.outlet == OUTLET_SYSTEM,
                    )
                    .group_by(UserTokenUsage.user_id)
                )
            ).all()
            used_map = {row[0]: int(row[1]) for row in used_rows}
            byok_ids = set(
                (
                    await self.session.execute(
                        select(UserLlmConfig.user_id).where(
                            UserLlmConfig.user_id.in_(ids)
                        )
                    )
                )
                .scalars()
                .all()
            )

        rows: list[dict[str, Any]] = []
        for user in users:
            quota = quotas.get(user.id)
            total = quota.total_tokens if quota is not None else 0
            unlimited = total is None or (user.role == "admin" and admin_exempt)
            used = used_map.get(user.id, 0)
            rows.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "status": user.status,
                    "application_note": user.application_note,
                    "reject_reason": user.reject_reason,
                    "last_login_at": user.last_login_at,
                    "created_at": user.created_at,
                    "remaining_quota": None if unlimited else int(total or 0) - used,
                    "total_used": used,
                    "byok_enabled": user.id in byok_ids,
                }
            )
        return rows

    async def update_user(self, user_id: int, data: AdminUserUpdate) -> User:
        """更新用户信息，缺失时抛 NotFoundError。"""
        user = await self.get_user(user_id)

        if data.username is not None and data.username != user.username:
            if await self.repo.exists_by_username(data.username):
                raise BadRequestError(f"Username {data.username} already exists")
            user.username = data.username
        if data.email is not None and data.email != user.email:
            if await self.repo.exists_by_email(data.email):
                raise BadRequestError(f"Email {data.email} already exists")
            user.email = data.email
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active

        await self.session.commit()
        await self.repo.refresh(user)
        return user

    async def delete_user(self, user_id: int) -> None:
        """删除用户，缺失时抛 NotFoundError。"""
        user = await self.get_user(user_id)
        await self.repo.delete(user)
        await self.session.commit()

    async def reset_password(self, user_id: int, password: str) -> User:
        """重置用户密码，缺失时抛 NotFoundError。"""
        user = await self.get_user(user_id)
        user.password_hash = get_password_hash(password)
        await self.session.commit()
        await self.repo.refresh(user)
        return user
