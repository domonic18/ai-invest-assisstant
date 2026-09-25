"""注册审批与配额管理服务（后台，全动作入审计，arch/07 §6.3 / §4.4）。"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.account_quota import UserAiQuota
from app.models.user import User
from app.services.admin.audit_service import record_audit
from app.services.quota import account_settings, quota_service
from app.services.quota.constants import (
    AUDIT_QUOTA_ADJUST,
    AUDIT_REGISTER_APPROVE,
    AUDIT_REGISTER_REJECT,
    AUDIT_SETTING_UPDATE,
    SETTING_ADMIN_EXEMPT,
)
from app.services.user.register_service import RegisterService

logger = structlog.get_logger(__name__)


class ApprovalService:
    """待审队列、审批动作与配额调整。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pending(self) -> list[dict[str, Any]]:
        """待审队列（申请时间升序；顺带惰性清理超期申请）。"""
        register = RegisterService(self.session)
        await register.cleanup_expired_pending()
        rows = (
            (
                await self.session.execute(
                    select(User)
                    .where(User.status == "pending")
                    .order_by(User.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": row.id,
                "username": row.username,
                "email": row.email,
                "application_note": row.application_note,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    async def pending_count(self) -> int:
        """待审数（角标；顺带惰性清理）。"""
        register = RegisterService(self.session)
        await register.cleanup_expired_pending()
        return await register.count_pending()

    async def approve(
        self,
        admin: User,
        user_id: int,
        initial_quota_tokens: int | None = None,
        ip: str | None = None,
    ) -> None:
        """通过申请：status → approved + 发初始配额（缺省取全局默认）+ 审计。

        Raises:
            NotFoundError: 用户不存在或不在待审状态。
        """
        user = await self._get_pending(user_id)
        if initial_quota_tokens is None:
            initial_quota_tokens = await account_settings.get_default_quota_tokens(
                self.session
            )
        now = utc_now()
        user.status = "approved"
        user.reject_reason = None
        user.reviewed_by = admin.id
        user.reviewed_at = now
        quota = await self.session.get(UserAiQuota, user.id)
        if quota is None:
            quota = UserAiQuota(user_id=user.id)
            self.session.add(quota)
        quota.total_tokens = initial_quota_tokens
        quota.updated_by = admin.id
        await record_audit(
            self.session,
            actor_id=admin.id,
            action=AUDIT_REGISTER_APPROVE,
            target_user_id=user.id,
            detail={"initialQuotaTokens": initial_quota_tokens},
            ip=ip,
        )
        await self.session.commit()
        logger.info(
            "register_approved",
            admin_id=admin.id,
            user_id=user.id,
            initial_quota_tokens=initial_quota_tokens,
        )

    async def reject(
        self, admin: User, user_id: int, reason: str, ip: str | None = None
    ) -> None:
        """驳回申请：reason 必填 + 审计（用户名/邮箱不永久占位，可重新申请）。

        Raises:
            NotFoundError: 用户不存在或不在待审状态。
            BadRequestError: 驳回原因为空。
        """
        if not reason.strip():
            raise BadRequestError("驳回原因不能为空")
        user = await self._get_pending(user_id)
        user.status = "rejected"
        user.reject_reason = reason.strip()
        user.reviewed_by = admin.id
        user.reviewed_at = utc_now()
        await record_audit(
            self.session,
            actor_id=admin.id,
            action=AUDIT_REGISTER_REJECT,
            target_user_id=user.id,
            detail={"reason": reason.strip()},
            ip=ip,
        )
        await self.session.commit()
        logger.info("register_rejected", admin_id=admin.id, user_id=user.id)

    async def adjust_quota(
        self,
        admin: User,
        user_id: int,
        *,
        action: str,
        delta_tokens: int | None = None,
        ip: str | None = None,
    ) -> UserAiQuota:
        """调整用户配额：adjust（追加/核减）或 reset（重置为全局默认）+ 审计 + 镜像失效。

        Raises:
            NotFoundError: 用户不存在。
            BadRequestError: action 非法或 delta 缺失。
        """
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("用户不存在")
        quota = await self.session.get(UserAiQuota, user_id)
        if quota is None:
            quota = UserAiQuota(user_id=user_id)
            self.session.add(quota)
        old_total = quota.total_tokens

        if action == "reset":
            quota.total_tokens = await account_settings.get_default_quota_tokens(
                self.session
            )
        elif action == "adjust":
            if delta_tokens is None:
                raise BadRequestError("adjust 需要 deltaTokens（正数追加、负数核减）")
            base = old_total if old_total is not None else 0
            new_total = base + delta_tokens
            quota.total_tokens = new_total if new_total > 0 else None
        else:
            raise BadRequestError("action 仅支持 adjust / reset")

        quota.updated_by = admin.id
        await record_audit(
            self.session,
            actor_id=admin.id,
            action=AUDIT_QUOTA_ADJUST,
            target_user_id=user_id,
            detail={
                "oldTotal": old_total,
                "newTotal": quota.total_tokens,
                "delta": delta_tokens,
                "scope": action,
            },
            ip=ip,
        )
        await self.session.commit()
        await quota_service.invalidate(user_id)
        return quota

    async def apply_settings(
        self, admin: User, updates: dict[str, Any], ip: str | None = None
    ) -> None:
        """批量 upsert 全局设置 + 审计（记录新旧值）+ 豁免开关变更后失效全部镜像。

        Raises:
            KeyError: updates 含未知设置键。
        """
        if not updates:
            return
        current = await account_settings.list_settings(self.session)
        changes = {
            key: {"oldValue": current.get(key), "newValue": value}
            for key, value in updates.items()
        }
        for key, value in updates.items():
            await account_settings.update_setting(
                self.session, key, value, updated_by=admin.id
            )
        await record_audit(
            self.session,
            actor_id=admin.id,
            action=AUDIT_SETTING_UPDATE,
            detail=changes,
            ip=ip,
        )
        await self.session.commit()
        if SETTING_ADMIN_EXEMPT in updates:
            await quota_service.invalidate_all()
        logger.info(
            "account_settings_updated", admin_id=admin.id, keys=sorted(updates)
        )

    async def _get_pending(self, user_id: int) -> User:
        user = await self.session.get(User, user_id)
        if user is None or user.status != "pending":
            raise NotFoundError("待审申请不存在或已处理")
        return user
