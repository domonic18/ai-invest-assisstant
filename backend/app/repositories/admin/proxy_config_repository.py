"""代理服务器配置仓储。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy_config import ProxyConfig
from app.repositories.base import BaseRepository


class ProxyConfigRepository(BaseRepository[ProxyConfig]):
    """代理服务器配置的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ProxyConfig)

    async def list_ordered(self) -> list[ProxyConfig]:
        """返回全部代理配置，按 id 排序。"""
        result = await self.execute(select(ProxyConfig).order_by(ProxyConfig.id))
        return list(result.scalars().all())

    async def exists_by_name(self, name: str, *, exclude_id: int | None = None) -> bool:
        """判断代理名称是否已被其它配置占用。"""
        stmt = select(ProxyConfig.id).where(ProxyConfig.name == name)
        if exclude_id is not None:
            stmt = stmt.where(ProxyConfig.id != exclude_id)
        result = await self.execute(stmt)
        return result.scalar_one_or_none() is not None
