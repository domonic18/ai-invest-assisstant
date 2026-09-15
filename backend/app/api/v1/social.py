"""社媒大 V 情绪用户侧 API（平台级共享视图，资讯中心第四 Tab 数据源）。

合规边界：任何响应模型不含 transcript_text（临时文稿判后即清）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.dependencies import get_db
from app.schemas.social import (
    SocialAccountsResponse,
    SocialFeedResponse,
    SocialTimelineResponse,
)
from app.services.social import feed_service

router = APIRouter()


@router.get("/sentiment-feed", response_model=SocialFeedResponse)
async def get_sentiment_feed(
    session: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(None, description="账号分类过滤"),
    stance: str | None = Query(None, pattern="^(bullish|bearish|neutral)$"),
    hours: int | None = Query(None, ge=1, le=168, description="只看近 N 小时"),
    strong_only: bool = Query(False, description="仅强信号（置信度≥0.8）"),
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> SocialFeedResponse:
    """情绪流：已判相关内容分页（新内容优先）。"""
    return await feed_service.get_feed(
        session,
        category=category,
        stance=stance,
        hours=hours,
        strong_only=strong_only,
        page=page,
        page_size=page_size,
    )


@router.get("/accounts", response_model=SocialAccountsResponse)
async def get_accounts(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SocialAccountsResponse:
    """账号维度卡（近 7 日多空分布 + 最新判断）。"""
    return await feed_service.get_account_cards(session)


@router.get("/accounts/{account_id}/timeline", response_model=SocialTimelineResponse)
async def get_account_timeline(
    account_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> SocialTimelineResponse:
    """单账号已判内容时间线（立场轨迹由前端按序派生）。"""
    return await feed_service.get_timeline(
        session, account_id, page=page, page_size=page_size
    )
