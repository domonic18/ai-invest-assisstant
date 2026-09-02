"""财联社电报查询仓储。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_telegraph import NewsTelegraph


async def list_telegraph(
    session: AsyncSession,
    page: int,
    page_size: int,
    category: str | None = None,
    min_importance: int | None = None,
) -> tuple[list[NewsTelegraph], int]:
    """分页查询电报，按 publish_time 降序。

    Args:
        session: 数据库会话。
        page: 页码（1 起）。
        page_size: 每页条数。
        category: 分类精确筛选（None 不过滤）。
        min_importance: 重要度下限筛选（None 不过滤）。

    Returns:
        (当前页电报列表, 总条数)。
    """
    conditions = []
    if category:
        conditions.append(NewsTelegraph.category == category)
    if min_importance is not None:
        conditions.append(NewsTelegraph.importance >= min_importance)

    count_stmt = select(func.count()).select_from(NewsTelegraph)
    stmt = select(NewsTelegraph)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        stmt = stmt.where(*conditions)

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = (
        stmt.order_by(NewsTelegraph.publish_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, total
