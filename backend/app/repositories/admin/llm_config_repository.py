"""LLM 配置仓储。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMConfig
from app.repositories.base import BaseRepository


class LLMConfigRepository(BaseRepository[LLMConfig]):
    """LLM 配置的数据访问（纯注册表：无默认/备用语义，选择权在选择点）。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LLMConfig)

    async def list_ordered(self) -> list[LLMConfig]:
        """返回全部配置，按 id 排序。"""
        stmt = select(LLMConfig).order_by(LLMConfig.id)
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def list_vision_active(self) -> list[LLMConfig]:
        """返回启用状态且标记视觉能力的配置，按 id 排序。"""
        stmt = (
            select(LLMConfig)
            .where(
                LLMConfig.is_active.is_(True),
                LLMConfig.extra["capabilities"]["vision"].as_boolean().is_(True),
            )
            .order_by(LLMConfig.id)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def list_decision_active(self) -> list[LLMConfig]:
        """返回启用状态的判断模型配置（purpose=decision，D23），按 id 排序。"""
        stmt = (
            select(LLMConfig)
            .where(LLMConfig.is_active.is_(True), LLMConfig.purpose == "decision")
            .order_by(LLMConfig.id)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())
