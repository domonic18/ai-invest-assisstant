"""追踪账号仓储（social_account 查询；写入由服务层持有事务）。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social import SocialAccount


async def get(session: AsyncSession, account_id: int) -> SocialAccount | None:
    """按主键取账号。"""
    result = await session.execute(select(SocialAccount).where(SocialAccount.id == account_id))
    return result.scalars().first()


async def get_by_sec_uid(
    session: AsyncSession, platform: str, sec_uid: str
) -> SocialAccount | None:
    """按 (platform, sec_uid) 唯一键取账号。"""
    result = await session.execute(
        select(SocialAccount).where(
            SocialAccount.platform == platform,
            SocialAccount.sec_uid == sec_uid,
        )
    )
    return result.scalars().first()


async def list_accounts(
    session: AsyncSession, *, active_only: bool = False
) -> list[SocialAccount]:
    """全量账号清单（平台级共享视图）；active_only 过滤启用的账号。"""
    stmt = select(SocialAccount).order_by(SocialAccount.id)
    if active_only:
        stmt = stmt.where(SocialAccount.is_active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())
