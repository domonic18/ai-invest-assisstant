"""用户业务服务。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.user.user_repository import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.user import MovingAverageConfig, UserSettings, UserSettingsUpdate

DEFAULT_MA_CONFIGS: list[MovingAverageConfig] = [
    MovingAverageConfig(period=5, color="#f0b429", enabled=True),
    MovingAverageConfig(period=10, color="#9d7ff5", enabled=True),
    MovingAverageConfig(period=20, color="#3fb6e0", enabled=True),
    MovingAverageConfig(period=30, color="#e8833a", enabled=True),
    MovingAverageConfig(period=60, color="#c0c4d0", enabled=False),
    MovingAverageConfig(period=120, color="#22c55e", enabled=False),
]


class UserService:
    """用户业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    @staticmethod
    def _default_settings() -> UserSettings:
        """返回默认用户配置。"""
        return UserSettings(ma_configs=DEFAULT_MA_CONFIGS)

    @staticmethod
    def _parse_settings(raw: Any) -> UserSettings:
        """解析原始 JSON 配置，失败时回退默认值。"""
        if not isinstance(raw, dict):
            return UserService._default_settings()
        try:
            return UserSettings.model_validate(raw)
        except Exception:
            return UserService._default_settings()

    async def get_settings(self, user: User) -> UserSettings:
        """获取用户个人配置，未设置时返回默认值。"""
        return self._parse_settings(user.settings)

    async def update_settings(self, user: User, data: UserSettingsUpdate) -> UserSettings:
        """更新用户个人配置。"""
        validated = UserSettings.model_validate(data)
        user.settings = validated.model_dump()
        await self.session.commit()
        return validated

    async def has_users(self) -> bool:
        """检查是否已存在至少一个用户。"""
        return (await self.repo.count()) > 0

    async def get_user_by_username(self, username: str) -> User | None:
        """通过用户名查询用户。"""
        return await self.repo.get_by_username(username)

    async def get_user_by_email(self, email: str) -> User | None:
        """通过邮箱查询用户。"""
        return await self.repo.get_by_email(email)

    async def create_user(self, data: RegisterRequest) -> User:
        """创建新用户。

        首个注册的账号会被授予 ``admin`` 角色，确保始终存在可访问管理后台的管理员。
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
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.commit()
