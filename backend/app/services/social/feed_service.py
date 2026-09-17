"""情绪流读服务（资讯中心第四 Tab：feed / 账号卡 / 单账号时间线）。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.social import post_repository
from app.schemas.social import (
    SocialAccountCardResponse,
    SocialAccountsResponse,
    SocialFeedItemResponse,
    SocialFeedResponse,
    SocialTimelineItemResponse,
    SocialTimelineResponse,
)


async def get_feed(
    session: AsyncSession,
    *,
    category: str | None = None,
    stance: str | None = None,
    hours: int | None = None,
    strong_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> SocialFeedResponse:
    """情绪流：已判相关内容分页（新内容优先）。"""
    items, total = await post_repository.list_feed(
        session,
        category=category,
        stance=stance,
        hours=hours,
        strong_only=strong_only,
        page=page,
        page_size=page_size,
    )
    return SocialFeedResponse(
        items=[SocialFeedItemResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_account_cards(
    session: AsyncSession, *, hours: int | None = 168
) -> SocialAccountsResponse:
    """账号维度卡（统计窗口内多空分布与按日时序 + 最新判断）。"""
    cards = await post_repository.list_account_cards(session, hours=hours)
    return SocialAccountsResponse(
        accounts=[SocialAccountCardResponse.model_validate(card) for card in cards]
    )


async def get_timeline(
    session: AsyncSession, account_id: int, *, page: int = 1, page_size: int = 20
) -> SocialTimelineResponse:
    """单账号已判内容时间线（立场轨迹由前端按序派生）。"""
    items, total = await post_repository.list_timeline(
        session, account_id, page=page, page_size=page_size
    )
    return SocialTimelineResponse(
        items=[SocialTimelineItemResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
