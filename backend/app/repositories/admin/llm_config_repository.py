"""LLM 配置仓储。"""

from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMConfig
from app.repositories.base import BaseRepository


class LLMConfigRepository(BaseRepository[LLMConfig]):
    """LLM 配置的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LLMConfig)

    async def list_ordered(self) -> list[LLMConfig]:
        """返回全部配置，默认配置优先，再按 id 排序。"""
        stmt = select(LLMConfig).order_by(LLMConfig.is_default.desc(), LLMConfig.id)
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_default_active(self) -> LLMConfig | None:
        """返回启用状态的默认配置，若不存在则为 None。"""
        stmt = select(LLMConfig).where(
            LLMConfig.is_default.is_(True),
            LLMConfig.is_active.is_(True),
        )
        result = await self.execute(stmt)
        return cast(LLMConfig | None, result.scalar_one_or_none())

    async def clear_other_defaults(self, exclude_id: int | None = None) -> None:
        """清除其余全部配置的默认标记。"""
        stmt = update(LLMConfig).values(is_default=False)
        if exclude_id is not None:
            stmt = stmt.where(LLMConfig.id != exclude_id)
        await self.execute(stmt)

    async def get_first_active(self) -> LLMConfig | None:
        """按 id 排序返回第一个启用状态的配置。"""
        stmt = (
            select(LLMConfig)
            .where(LLMConfig.is_active.is_(True))
            .order_by(LLMConfig.id)
            .limit(1)
        )
        result = await self.execute(stmt)
        return cast(LLMConfig | None, result.scalar_one_or_none())
