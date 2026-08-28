"""LLM configuration repository."""

from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMConfig
from app.repositories.base import BaseRepository


class LLMConfigRepository(BaseRepository[LLMConfig]):
    """Data access for LLM configurations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LLMConfig)

    async def list_ordered(self) -> list[LLMConfig]:
        """Return all configs ordered by default first, then id."""
        stmt = select(LLMConfig).order_by(LLMConfig.is_default.desc(), LLMConfig.id)
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_default_active(self) -> LLMConfig | None:
        """Return the active default configuration, if any."""
        stmt = select(LLMConfig).where(
            LLMConfig.is_default.is_(True),
            LLMConfig.is_active.is_(True),
        )
        result = await self.execute(stmt)
        return cast(LLMConfig | None, result.scalar_one_or_none())

    async def clear_other_defaults(self, exclude_id: int | None = None) -> None:
        """Clear the default flag from all other configurations."""
        stmt = update(LLMConfig).values(is_default=False)
        if exclude_id is not None:
            stmt = stmt.where(LLMConfig.id != exclude_id)
        await self.execute(stmt)

    async def get_first_active(self) -> LLMConfig | None:
        """Return the first active configuration ordered by id."""
        stmt = (
            select(LLMConfig)
            .where(LLMConfig.is_active.is_(True))
            .order_by(LLMConfig.id)
            .limit(1)
        )
        result = await self.execute(stmt)
        return cast(LLMConfig | None, result.scalar_one_or_none())
