"""助手会话仓储。"""

import uuid
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_session import AssistantSession
from app.repositories.base import BaseRepository


class AssistantSessionRepository(BaseRepository[AssistantSession]):
    """assistant_session 的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AssistantSession)

    async def list_by_user(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> tuple[list[AssistantSession], int]:
        """当前用户会话列表（最近活跃优先）与总数。"""
        rows = (
            await self.execute(
                select(AssistantSession)
                .where(AssistantSession.user_id == user_id)
                .order_by(
                    AssistantSession.last_message_at.desc().nulls_last(),
                    AssistantSession.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        total = (
            await self.scalar(
                select(func.count())
                .select_from(AssistantSession)
                .where(AssistantSession.user_id == user_id)
            )
        )
        return list(rows), int(total or 0)

    async def get_by_user_and_thread(
        self, user_id: int, thread_id: uuid.UUID
    ) -> AssistantSession | None:
        """按归属取会话（thread_id 已是合法 UUID，非本人返回 None）。"""
        stmt = select(AssistantSession).where(
            AssistantSession.id == thread_id,
            AssistantSession.user_id == user_id,
        )
        result = await self.execute(stmt)
        return cast(AssistantSession | None, result.scalar_one_or_none())
