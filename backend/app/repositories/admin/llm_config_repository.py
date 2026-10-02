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
        """返回启用状态的默认 chat 配置，若不存在则为 None。

        purpose 过滤防止其他用途（embedding/decision 等）条目被置默认后
        劫持 chat 解析——``build_langchain_model`` 收到 systemone 协议会直接失败。
        """
        stmt = select(LLMConfig).where(
            LLMConfig.is_default.is_(True),
            LLMConfig.is_active.is_(True),
            LLMConfig.purpose == "chat",
        )
        result = await self.execute(stmt)
        return cast(LLMConfig | None, result.scalar_one_or_none())

    async def clear_other_defaults(self, exclude_id: int | None = None) -> None:
        """清除其余全部配置的默认标记。"""
        stmt = update(LLMConfig).values(is_default=False)
        if exclude_id is not None:
            stmt = stmt.where(LLMConfig.id != exclude_id)
        await self.execute(stmt)

    async def clear_backup_references(self, config_id: int) -> None:
        """清除指向给定配置的全部备用引用（删除条目前调用）。"""
        stmt = (
            update(LLMConfig)
            .where(LLMConfig.backup_config_id == config_id)
            .values(backup_config_id=None)
        )
        await self.execute(stmt)

    async def get_first_active(self) -> LLMConfig | None:
        """按 id 排序返回第一个启用状态的 chat 配置（默认配置删除后重指之用）。"""
        stmt = (
            select(LLMConfig)
            .where(LLMConfig.is_active.is_(True), LLMConfig.purpose == "chat")
            .order_by(LLMConfig.id)
            .limit(1)
        )
        result = await self.execute(stmt)
        return cast(LLMConfig | None, result.scalar_one_or_none())

    async def list_vision_active(self) -> list[LLMConfig]:
        """返回启用状态且标记视觉能力的配置，默认配置优先。"""
        stmt = (
            select(LLMConfig)
            .where(
                LLMConfig.is_active.is_(True),
                LLMConfig.extra["capabilities"]["vision"].as_boolean().is_(True),
            )
            .order_by(LLMConfig.is_default.desc(), LLMConfig.id)
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
