"""管理端审计日志：审批、配额调整、全局设置变更全量留痕。"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_quota import AdminAuditLog

logger = structlog.get_logger(__name__)


async def record_audit(
    session: AsyncSession,
    *,
    actor_id: int,
    action: str,
    target_user_id: int | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """写一条审计记录（随调用方事务一起提交）。"""
    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action=action,
            target_user_id=target_user_id,
            detail=detail or {},
            ip=ip,
        )
    )
    logger.info(
        "admin_audit",
        actor_id=actor_id,
        action=action,
        target_user_id=target_user_id,
        detail=detail or {},
    )
