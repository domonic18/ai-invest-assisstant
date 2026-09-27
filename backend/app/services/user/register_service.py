"""注册申请服务（arch/07 §6）：注册改申请 + IP 限流 + 惰性过期清理。

- 同 username/email 已有 pending 申请 → 409「已有申请在审」；
- 已有 rejected 记录 → 复用该行重置回 pending（新密码/新说明/清驳回原因，
  驳回不永久占位，用户零求助重新申请）；
- 已有 approved 账号 → 409「已注册」；
- 新建 status='pending'，不签发任何登录凭证。
"""

from datetime import timedelta

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import register_throttle
from app.core.clock import utc_now
from app.core.exceptions import ConflictError, TooManyRequestsError
from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user.user_repository import UserRepository
from app.schemas.auth import RegisterAccepted, RegisterRequest
from app.services.quota import account_settings

logger = structlog.get_logger(__name__)


class RegisterService:
    """注册申请业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def submit(self, data: RegisterRequest, client_ip: str) -> RegisterAccepted:
        """提交注册申请（IP 限流 → 冲突判定 → 建号/重置 pending）。

        Raises:
            TooManyRequestsError: 该 IP 今日提交次数达到上限。
            ConflictError: 同 username/email 已有在审申请或已注册账号。
        """
        if not await register_throttle.check_ip_allowed(client_ip):
            raise TooManyRequestsError("注册提交过于频繁，请明日再试")

        await self.cleanup_expired_pending()

        existing = await self._find_conflict(data.username, data.email)
        if existing is not None:
            if existing.status == "pending":
                raise ConflictError("该用户名或邮箱已有申请在审，请等待管理员处理")
            if existing.status == "approved":
                raise ConflictError("该用户名或邮箱已注册")
            # rejected：复用行重置回 pending（清驳回原因与审批痕迹）
            existing.password_hash = get_password_hash(data.password)
            existing.application_note = data.application_note
            existing.reject_reason = None
            existing.reviewed_by = None
            existing.reviewed_at = None
            existing.status = "pending"
            await self.session.commit()
        else:
            user = User(
                username=data.username,
                email=data.email,
                password_hash=get_password_hash(data.password),
                role="user",
                status="pending",
                application_note=data.application_note,
            )
            self.repo.add(user)
            await self.session.commit()

        await register_throttle.record_submission(client_ip)
        logger.info(
            "register_submitted",
            username=data.username,
            client_ip=client_ip,
            resubmit=existing is not None,
        )
        return RegisterAccepted()

    async def _find_conflict(self, username: str, email: str) -> User | None:
        """按用户名或邮箱查找既有账号（pending/approved/rejected 均算占用）。"""
        result = await self.session.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        return result.scalar_one_or_none()

    async def cleanup_expired_pending(self) -> int:
        """惰性清理超期 pending 申请（N 天无审批即过期），返回清理行数。"""
        expire_days = await account_settings.get_pending_expire_days(self.session)
        cutoff = utc_now() - timedelta(days=expire_days)
        result = await self.session.execute(
            delete(User).where(User.status == "pending", User.created_at < cutoff)
        )
        deleted = int(getattr(result, "rowcount", 0) or 0)
        if deleted:
            await self.session.commit()
            logger.info("register_pending_expired_cleaned", count=deleted)
        return deleted

    async def count_pending(self) -> int:
        """当前待审申请数（后台角标）。"""
        result = await self.session.execute(
            select(func.count()).select_from(User).where(User.status == "pending")
        )
        return int(result.scalar_one() or 0)
