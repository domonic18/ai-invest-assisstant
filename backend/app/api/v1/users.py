"""用户与自选股 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.market import WatchlistQuoteItem
from app.schemas.user import (
    PasswordChangeRequest,
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
    UserUpdate,
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
    recognize_screenshot,
)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """获取当前登录用户信息。"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """更新当前用户信息（邮箱）。"""
    user = await UserService(session).update_email(current_user, data.email)
    return UserResponse.model_validate(user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_me_password(
    data: PasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """修改当前用户密码（旧 token 无黑名单，前端改密成功后引导重新登录）。"""
    await UserService(session).change_password(
        current_user, data.current_password, data.new_password
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


@router.post("/watchlist", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
async def add_watchlist(
    data: WatchlistItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistItemResponse:
    """添加自选股（导入后服务内部触发日 K 回补）。"""
    item = await WatchlistService(session).add_watchlist_item(current_user, data)
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
    items = await recognize_screenshot(session, data, file.content_type)
    return WatchlistScreenshotRecognitionResponse(items=items)


@router.post(
    "/watchlist/batch", response_model=WatchlistBatchResponse, status_code=status.HTTP_201_CREATED
)
async def batch_add_watchlist(
    data: WatchlistBatchCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistBatchResponse:
    """批量导入自选股（截图识别确认后的目标分组落库；新增项服务内部触发日 K 回补）。"""
    return await WatchlistService(session).batch_add_items(current_user, data)


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


@router.post(
    "/watchlist/groups",
    response_model=WatchlistGroupWithItemsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_watchlist_group(
    data: WatchlistGroupCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistGroupWithItemsResponse:
    """创建自选股分组。"""
    group = await WatchlistService(session).create_group(current_user.id, data)
    return WatchlistGroupWithItemsResponse.model_validate(group)


@router.patch("/watchlist/groups/{group_id}", response_model=WatchlistGroupWithItemsResponse)
async def update_watchlist_group(
    group_id: int,
    data: WatchlistGroupUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistGroupWithItemsResponse:
    """更新分组（改名/排序值由重排接口维护/AI 复盘开关）。"""
    group = await WatchlistService(session).update_group(current_user.id, group_id, data)
    return WatchlistGroupWithItemsResponse.model_validate(group)


@router.delete("/watchlist/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_group(
    group_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除分组（组内股票移入默认分组）。"""
    await WatchlistService(session).delete_group(current_user.id, group_id)


@router.put("/watchlist/groups/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_watchlist_groups(
    data: WatchlistGroupReorderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """按传入顺序整体重排分组。"""
    await WatchlistService(session).reorder_groups(current_user.id, data.group_ids)


@router.patch("/watchlist/items/{item_id}", response_model=WatchlistItemResponse)
async def move_watchlist_item(
    item_id: int,
    data: WatchlistItemMoveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WatchlistItemResponse:
    """移动自选股到目标分组。"""
    item = await WatchlistService(session).move_watchlist_item(
        current_user.id, item_id, data.group_id
    )
    return WatchlistItemResponse.model_validate(item)


@router.delete("/watchlist/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除自选股。"""
    await WatchlistService(session).remove_watchlist_item(current_user.id, item_id)
