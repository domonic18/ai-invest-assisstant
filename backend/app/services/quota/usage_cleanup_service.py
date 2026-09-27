"""用量记录手动清理：管理员触发的保留窗口治理（arch/07 §7）。

看板/明细聚合窗口最长 90 天（days 参数钳制），删除 180 天前记录不影响
任何展示口径；操作随事务写入审计日志。
"""

from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.models.account_quota import UserTokenUsage
from app.services.admin import audit_service

RETENTION_DAYS = 180


async def cleanup_token_usage(
    session: AsyncSession,
    *,
    actor_id: int,
    ip: str | None = None,
    retention_days: int = RETENTION_DAYS,
) -> int:
    """删除 retention_days 天前的 token 用量记录，返回删除行数（入审计）。"""
    cutoff = utc_now() - timedelta(days=retention_days)
    result = await session.execute(
        delete(UserTokenUsage).where(UserTokenUsage.created_at < cutoff)
    )
    removed = int(getattr(result, "rowcount", 0) or 0)
    await audit_service.record_audit(
        session,
        actor_id=actor_id,
        action="usage.cleanup",
        detail={"retention_days": retention_days, "removed_count": removed},
        ip=ip,
    )
    await session.commit()
    return removed
