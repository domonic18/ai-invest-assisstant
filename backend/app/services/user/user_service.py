"""用户业务服务。"""

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import login_throttle
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    LoginLockedError,
    UnauthorizedError,
)
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.user.user_repository import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.user import MovingAverageConfig, UserSettings, UserSettingsUpdate

logger = structlog.get_logger(__name__)

DEFAULT_MA_CONFIGS: list[MovingAverageConfig] = [
    MovingAverageConfig(period=5, color="#f0b429", enabled=True),
    MovingAverageConfig(period=10, color="#9d7ff5", enabled=True),
    MovingAverageConfig(period=20, color="#3fb6e0", enabled=True),
    MovingAverageConfig(period=30, color="#e8833a", enabled=True),
    MovingAverageConfig(period=60, color="#c0c4d0", enabled=True),
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
            logger.warning("user_settings_parse_failed_fallback_defaults")
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

    async def get_user_by_username(self, username: str) -> User | None:
        """通过用户名查询用户。"""
        return await self.repo.get_by_username(username)

    async def get_user_by_email(self, email: str) -> User | None:
        """通过邮箱查询用户。"""
        return await self.repo.get_by_email(email)

    async def create_user(self, data: RegisterRequest) -> User:
        """创建新用户（一律 ``user`` 角色；管理员经 ``python -m app.cli.bootstrap_admin`` 显式提权）。"""
        user = User(
            username=data.username,
            email=data.email,
            password_hash=get_password_hash(data.password),
            role="user",
        )
        self.repo.add(user)
        await self.session.commit()
        await self.repo.refresh(user)
        return user

    async def attempt_login(self, username: str, password: str, client_ip: str = "-") -> User:
        """登录编排：防爆破检查 → 认证 → 失败计数/成功清零 + 审计日志。

        Raises:
            LoginLockedError: 该 (用户名, IP) 连续失败达阈值，处于锁定窗口。
            UnauthorizedError: 用户名或密码错误（已记失败计数与审计日志）。
        """
        lock = await login_throttle.locked_seconds(username, client_ip)
        if lock > 0:
            logger.warning(
                "login_locked", username=username, client_ip=client_ip, retry_after=lock
            )
            raise LoginLockedError(
                retry_after=lock, message=f"失败次数过多，账号已临时锁定，请 {lock} 秒后重试"
            )

        user = await self.authenticate_user(username, password)
        if user is None:
            await login_throttle.record_failure(username, client_ip)
            logger.warning("login_failed", username=username, client_ip=client_ip)
            raise UnauthorizedError("Incorrect username or password")

        await login_throttle.reset_failures(username, client_ip)
        logger.info("login_succeeded", username=username, client_ip=client_ip)
        return user

    async def authenticate_user(self, username: str, password: str) -> User | None:
        """验证用户名和密码。"""
        user = await self.get_user_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user

    async def update_email(self, user: User, email: str) -> User:
        """更新当前用户邮箱（全局唯一）。

        Raises:
            ConflictError: 邮箱已被其他用户占用。
        """
        existing = await self.get_user_by_email(email)
        if existing is not None and existing.id != user.id:
            raise ConflictError("该邮箱已被使用")
        user.email = email
        await self.session.commit()
        await self.repo.refresh(user)
        return user

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        """修改当前用户密码（校验旧密码后重哈希）。

        Raises:
            BadRequestError: 当前密码不正确。
        """
        if not verify_password(current_password, user.password_hash):
            raise BadRequestError("当前密码不正确")
        user.password_hash = get_password_hash(new_password)
        await self.session.commit()

    async def update_last_login(self, user: User) -> None:
        """更新最后登录时间。"""
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.commit()
