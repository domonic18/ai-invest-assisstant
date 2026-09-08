"""财联社电报查询服务。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NEWS_SOURCE_TELEGRAPH
from app.repositories.market import telegraph_repository
from app.repositories.market.telegraph_repository import TelegraphRow
from app.repositories.news import ai_score_repository, subscription_repository
from app.schemas.news import ScoreFactorsResponse
from app.schemas.telegraph import TelegraphResponse


async def list_telegraph(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    min_importance: int | None = None,
    min_ai_score: int | None = None,
    subscription_only: bool = False,
    user_id: int | None = None,
) -> tuple[list[TelegraphRow], int]:
    """分页查询电报（publish_time 降序），返回 (当前页含 AI 分级, 总条数)。"""
    return await telegraph_repository.list_telegraph(
        session,
        page=page,
        page_size=page_size,
        category=category,
        min_importance=min_importance,
        min_ai_score=min_ai_score,
        subscription_user_id=user_id if subscription_only else None,
    )


def to_responses(
    rows: list[TelegraphRow],
    *,
    factors_map: dict[str, dict[str, Any]] | None = None,
    subscribed_ids: set[str] | None = None,
) -> list[TelegraphResponse]:
    """把 ``(电报行, ai_score, ai_scored_at)`` 映射为响应模型（电报页/工作台共用）。

    factors_map/subscribed_ids 可选回填（资讯中心电报流 ★ 标注与评分构成）。
    """
    items: list[TelegraphResponse] = []
    for item, ai_score, ai_scored_at in rows:
        response = TelegraphResponse.model_validate(item)
        response.ai_score = ai_score
        response.ai_scored_at = ai_scored_at
        detail = (factors_map or {}).get(str(item.cls_msg_id))
        if subscribed_ids is not None:
            response.subscribed = str(item.cls_msg_id) in subscribed_ids
        if detail:
            factors = detail.get("factors")
            if isinstance(factors, dict):
                response.ai_factors = ScoreFactorsResponse.model_validate(factors)
        items.append(response)
    return items


async def enrich_and_respond(
    session: AsyncSession,
    rows: list[TelegraphRow],
    *,
    user_id: int,
) -> list[TelegraphResponse]:
    """按当前页条目批量回填评分构成与订阅命中（电报流路由入口）。"""
    item_ids = [str(item.cls_msg_id) for item, _, _ in rows]
    if not item_ids:
        return []
    details = await ai_score_repository.score_details(
        session, source=NEWS_SOURCE_TELEGRAPH, item_ids=item_ids
    )
    subscribed_ids = await subscription_repository.hit_item_ids(
        session, user_id=user_id, source=NEWS_SOURCE_TELEGRAPH, item_ids=item_ids
    )
    return to_responses(rows, factors_map=details, subscribed_ids=subscribed_ids)
