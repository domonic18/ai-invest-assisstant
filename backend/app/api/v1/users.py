"""用户与自选股 API 路由。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.market import WatchlistQuoteItem
from app.schemas.user import (
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
    WatchlistBatchCreate,
    WatchlistBatchResponse,
    WatchlistGroupCreate,
    WatchlistGroupReorderRequest,
    WatchlistGroupUpdate,
    WatchlistGroupWithItemsResponse,
    WatchlistItemCreate,
    WatchlistItemMoveRequest,
    WatchlistItemResponse,
    WatchlistScreenshotRecognitionResponse,
)
from app.services.market import market_service
from app.services.user import UserService, WatchlistService
from app.services.user.screenshot_recognition_service import (
    ScreenshotValidationError,
    recognize_screenshot,
)
from app.services.user.watchlist_service import GroupLimitError

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


@router.post(
    "/watchlist/recognize-screenshot",
    response_model=WatchlistScreenshotRecognitionResponse,
)
async def recognize_watchlist_screenshot(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(description="股票截图（png/jpeg/webp，≤8MB）")],
) -> WatchlistScreenshotRecognitionResponse:
    """截图识别候选自选股：视觉模型识别 + stock_basic 交叉校验。"""
    data = await file.read()
    try:
        items = await recognize_screenshot(session, data, file.content_type)
    except ScreenshotValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return WatchlistScreenshotRecognitionResponse(items=items)


@router.post("/watchlist/batch", response_model=WatchlistBatchResponse)
async def batch_add_watchlist(
    data: WatchlistBatchCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistBatchResponse:
    """批量导入自选股（截图识别确认后的目标分组落库）。"""
    try:
        return await WatchlistService(session).batch_add_items(current_user, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/watchlist/quotes", response_model=list[WatchlistQuoteItem])
async def get_watchlist_quotes(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WatchlistQuoteItem]:
    """获取当前用户自选股实时行情（Redis 快照，缺失时回退最近收盘价）。"""
    return await market_service.get_watchlist_quotes(session, current_user.id)


@router.get("/watchlist/groups", response_model=list[WatchlistGroupWithItemsResponse])
async def get_watchlist_groups(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WatchlistGroupWithItemsResponse]:
    """获取当前用户分组及组内自选股（默认分组缺失时自动创建）。"""
    groups = await WatchlistService(session).list_groups_with_items(current_user.id)
    return [WatchlistGroupWithItemsResponse.model_validate(group) for group in groups]


@router.post("/watchlist/groups", response_model=WatchlistGroupWithItemsResponse)
async def create_watchlist_group(
    data: WatchlistGroupCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistGroupWithItemsResponse:
    """创建自选股分组。"""
    try:
        group = await WatchlistService(session).create_group(current_user.id, data)
    except GroupLimitError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return WatchlistGroupWithItemsResponse.model_validate(group)


@router.patch("/watchlist/groups/{group_id}", response_model=WatchlistGroupWithItemsResponse)
async def update_watchlist_group(
    group_id: int,
    data: WatchlistGroupUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistGroupWithItemsResponse:
    """更新分组（改名/排序值由重排接口维护/AI 复盘开关）。"""
    try:
        group = await WatchlistService(session).update_group(current_user.id, group_id, data)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return WatchlistGroupWithItemsResponse.model_validate(group)


@router.delete("/watchlist/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_group(
    group_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除分组（组内股票移入默认分组）。"""
    try:
        await WatchlistService(session).delete_group(current_user.id, group_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.put("/watchlist/groups/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_watchlist_groups(
    data: WatchlistGroupReorderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """按传入顺序整体重排分组。"""
    try:
        await WatchlistService(session).reorder_groups(current_user.id, data.group_ids)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.patch("/watchlist/items/{item_id}", response_model=WatchlistItemResponse)
async def move_watchlist_item(
    item_id: int,
    data: WatchlistItemMoveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistItemResponse:
    """移动自选股到目标分组。"""
    try:
        item = await WatchlistService(session).move_watchlist_item(
            current_user.id, item_id, data.group_id
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return WatchlistItemResponse.model_validate(item)


@router.delete("/watchlist/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除自选股。"""
    try:
        await WatchlistService(session).remove_watchlist_item(current_user.id, item_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
