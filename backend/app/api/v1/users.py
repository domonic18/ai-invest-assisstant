"""Users and watchlist API endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.market import WatchlistQuoteItem
from app.schemas.user import (
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
    WatchlistItemCreate,
    WatchlistItemResponse,
)
from app.services import market_service
from app.services.user_service import UserService
from app.services.watchlist_service import WatchlistService

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """获取当前登录用户信息。"""
    return current_user


@router.put("/me")
async def update_me() -> dict[str, Any]:
    """更新当前用户信息（占位实现）。"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User update is not implemented yet",
    )


@router.get("/me/settings", response_model=UserSettingsResponse)
async def get_me_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    """获取当前用户个人配置（K 线均线等），未设置时返回默认值。"""
    settings = await UserService(session).get_settings(current_user)
    return UserSettingsResponse.model_validate(settings)


@router.put("/me/settings", response_model=UserSettingsResponse)
async def update_me_settings(
    data: UserSettingsUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    """更新当前用户个人配置。"""
    settings = await UserService(session).update_settings(current_user, data)
    return UserSettingsResponse.model_validate(settings)


@router.get("/watchlist", response_model=list[WatchlistItemResponse])
async def get_watchlist(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WatchlistItemResponse]:
    """获取当前用户自选股。"""
    items = await WatchlistService(session).get_watchlist_by_user(current_user.id)
    return [WatchlistItemResponse.model_validate(item) for item in items]


@router.post("/watchlist", response_model=WatchlistItemResponse)
async def add_watchlist(
    data: WatchlistItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistItemResponse:
    """添加自选股。"""
    try:
        item = await WatchlistService(session).add_watchlist_item(current_user, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return WatchlistItemResponse.model_validate(item)


@router.get("/watchlist/quotes", response_model=list[WatchlistQuoteItem])
async def get_watchlist_quotes(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WatchlistQuoteItem]:
    """获取当前用户自选股实时行情（Redis 快照，缺失时回退最近收盘价）。"""
    return await market_service.get_watchlist_quotes(session, current_user.id)
