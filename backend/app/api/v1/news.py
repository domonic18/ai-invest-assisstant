"""资讯中心 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.news import NewsChannelsResponse
from app.services.news import news_channel_service

router = APIRouter()


@router.get("/channels", response_model=NewsChannelsResponse)
async def list_news_channels(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NewsChannelsResponse:
    """渠道监控卡 + 今日统计（注册表驱动，登录态）。"""
    return await news_channel_service.get_channels_status(session)
