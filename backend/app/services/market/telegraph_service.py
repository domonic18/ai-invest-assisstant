"""财联社电报查询服务。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_telegraph import NewsTelegraph
from app.repositories.market import telegraph_repository


async def list_telegraph(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    min_importance: int | None = None,
) -> tuple[list[NewsTelegraph], int]:
    """分页查询电报（publish_time 降序），返回 (当前页, 总条数)。"""
    return await telegraph_repository.list_telegraph(
        session,
        page=page,
        page_size=page_size,
        category=category,
        min_importance=min_importance,
    )
