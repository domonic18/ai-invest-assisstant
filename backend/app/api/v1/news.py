"""资讯中心 API 路由：渠道监控 + 重点/故事线 + 热点主题 + 我的订阅。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.news import (
    FocusResponse,
    NewsChannelsResponse,
    StorylineCreateRequest,
    StorylineDetailResponse,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
    TopicsResponse,
)
from app.services.news import (
    news_channel_service,
    storyline_service,
    subscription_service,
    topic_service,
)

router = APIRouter()


@router.get("/channels", response_model=NewsChannelsResponse)
async def list_news_channels(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NewsChannelsResponse:
    """渠道监控卡 + 今日统计（注册表驱动，登录态）。"""
    return await news_channel_service.get_channels_status(session)


@router.get("/focus", response_model=FocusResponse)
async def get_news_focus(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FocusResponse:
    """重点与跟踪视图：今日重点（含评分构成）+ 跟踪中故事线。"""
    return await storyline_service.get_focus(session, user_id=current_user.id)


@router.get("/topics", response_model=TopicsResponse)
async def get_news_topics(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    session_key: Annotated[
        str, Query(alias="session", description="intraday|post，默认 post")
    ] = "post",
) -> TopicsResponse:
    """当日热点主题快照（词云 + 主题卡榜）。"""
    key = session_key if session_key in ("intraday", "post") else "post"
    payload = await topic_service.get_topics(db, session_key=key)
    return TopicsResponse.model_validate(payload)


@router.get("/stories/{storyline_id}", response_model=StorylineDetailResponse)
async def get_news_story(
    storyline_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StorylineDetailResponse:
    """故事线详情：线卡 + 节点链 + 线内条目回显。"""
    return await storyline_service.get_story(
        session, user_id=current_user.id, storyline_id=storyline_id
    )


@router.post(
    "/stories",
    response_model=StorylineDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_news_story(
    payload: StorylineCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StorylineDetailResponse:
    """以单条资讯手动建线（origin=manual，仅本人视图）。"""
    storyline_id = await storyline_service.create_manual(
        session,
        user_id=current_user.id,
        source=payload.source,
        item_id=payload.item_id,
    )
    return await storyline_service.get_story(
        session, user_id=current_user.id, storyline_id=storyline_id
    )


@router.post("/stories/{storyline_id}/track", status_code=status.HTTP_204_NO_CONTENT)
async def track_news_story(
    storyline_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """加入跟踪（user_news_storyline upsert active）。"""
    await storyline_service.set_user_action(
        session, user_id=current_user.id, storyline_id=storyline_id, action="active"
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/stories/{storyline_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_news_story(
    storyline_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """停止跟踪（本人视图移除该线，AI 续接全局进行）。"""
    await storyline_service.set_user_action(
        session, user_id=current_user.id, storyline_id=storyline_id, action="stopped"
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_news_subscriptions(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SubscriptionResponse]:
    """我的订阅列表（含命中统计）。"""
    items = await subscription_service.list_for_user(session, user_id=current_user.id)
    return [SubscriptionResponse.model_validate(item) for item in items]


@router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_news_subscription(
    payload: SubscriptionCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubscriptionResponse:
    """新增关键词订阅。"""
    subscription = await subscription_service.create(
        session,
        user_id=current_user.id,
        keyword=payload.keyword,
        channels=payload.channels,
    )
    item = await subscription_service.with_hit_stats(session, subscription)
    return SubscriptionResponse.model_validate(item)


@router.patch(
    "/subscriptions/{subscription_id}", response_model=SubscriptionResponse
)
async def update_news_subscription(
    subscription_id: int,
    payload: SubscriptionUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubscriptionResponse:
    """更新订阅（渠道/推送开关/启停）。"""
    subscription = await subscription_service.update(
        session,
        user_id=current_user.id,
        subscription_id=subscription_id,
        channels=payload.channels,
        push_enabled=payload.push_enabled,
        enabled=payload.enabled,
    )
    item = await subscription_service.with_hit_stats(session, subscription)
    return SubscriptionResponse.model_validate(item)


@router.delete(
    "/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_news_subscription(
    subscription_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """删除订阅（级联删命中记录）。"""
    await subscription_service.delete(
        session, user_id=current_user.id, subscription_id=subscription_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
