"""财联社电报查询服务。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market import telegraph_repository
from app.repositories.market.telegraph_repository import TelegraphRow
from app.schemas.telegraph import TelegraphResponse


async def list_telegraph(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    min_importance: int | None = None,
    min_ai_score: int | None = None,
) -> tuple[list[TelegraphRow], int]:
    """分页查询电报（publish_time 降序），返回 (当前页含 AI 分级, 总条数)。"""
    return await telegraph_repository.list_telegraph(
        session,
        page=page,
        page_size=page_size,
        category=category,
        min_importance=min_importance,
        min_ai_score=min_ai_score,
    )


def to_responses(rows: list[TelegraphRow]) -> list[TelegraphResponse]:
    """把 ``(电报行, ai_score, ai_scored_at)`` 映射为响应模型（电报页/工作台共用）。"""
    items: list[TelegraphResponse] = []
    for item, ai_score, ai_scored_at in rows:
        response = TelegraphResponse.model_validate(item)
        response.ai_score = ai_score
        response.ai_scored_at = ai_scored_at
        items.append(response)
    return items
