"""K 线画线 API 路由（F-DRAW：用户画线 CRUD + AI 画线采纳）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.drawing import (
    AiKlineDrawingAdoptRequest,
    KlineDrawingsResponse,
    UserKlineDrawingCreateRequest,
    UserKlineDrawingResponse,
    UserKlineDrawingUpdateRequest,
)
from app.services.market.kline_drawing_service import KlineDrawingService

router = APIRouter()


@router.get("", response_model=KlineDrawingsResponse)
async def list_kline_drawings(
    target_type: str,
    target_code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> KlineDrawingsResponse:
    """该标的全周期 user + ai 画线（周期切换前端过滤，零请求）。"""
    service = KlineDrawingService(session)
    return await service.list_drawings(current_user.id, target_type, target_code)


@router.post("", response_model=UserKlineDrawingResponse, status_code=status.HTTP_201_CREATED)
async def create_kline_drawing(
    request: UserKlineDrawingCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserKlineDrawingResponse:
    """创建用户画线（锚点校验失败返回 400）。"""
    service = KlineDrawingService(session)
    return await service.create_user_drawing(current_user.id, request)


@router.patch("/{drawing_id}", response_model=UserKlineDrawingResponse)
async def update_kline_drawing(
    drawing_id: int,
    request: UserKlineDrawingUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserKlineDrawingResponse:
    """部分更新用户画线（形态/样式/文字），校验归属。"""
    service = KlineDrawingService(session)
    return await service.update_user_drawing(current_user.id, drawing_id, request)


@router.delete("/{drawing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kline_drawing(
    drawing_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """删除用户画线，校验归属。"""
    service = KlineDrawingService(session)
    await service.delete_user_drawing(current_user.id, drawing_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ai/adopt", response_model=UserKlineDrawingResponse, status_code=status.HTTP_201_CREATED)
async def adopt_ai_drawing(
    request: AiKlineDrawingAdoptRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserKlineDrawingResponse:
    """AI 画线单条采纳：按 label 定位，复制为用户画线（原 AI 画线保留）。"""
    service = KlineDrawingService(session)
    return await service.adopt_ai_drawing(current_user.id, request)
