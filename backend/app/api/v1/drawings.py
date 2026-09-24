"""K 线画线 API 路由（F-DRAW：用户画线 CRUD + AI 画线采纳）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.base import CamelModel
from app.schemas.drawing import (
    AiKlineDrawingAdoptRequest,
    AiKlineDrawingItemSchema,
    KlineDrawingAnchorSchema,
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


@router.delete("/ai/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_ai_drawings(
    target_type: str,
    target_code: str,
    period: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """清空当前用户在标的+周期的 AI 画线集（per-user 私有，对话重新生成即恢复）。

    注册在 ``/{drawing_id}`` 之前：DELETE /ai/clear 是字面路径，后置会被
    int 路径参数吞并成 422。
    """
    service = KlineDrawingService(session)
    await service.clear_ai_group(current_user.id, target_type, target_code, period)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class AiItemUpdateRequest(CamelModel):
    """AI 画线单条原位编辑（拖拽锚点 / 双击改名）。"""

    target_type: str
    target_code: str = Field(min_length=1, max_length=16)
    period: str
    label: str = Field(min_length=1, max_length=100)
    anchors: list[KlineDrawingAnchorSchema] | None = None
    new_label: str | None = Field(default=None, min_length=1, max_length=100)


@router.patch("/ai/item", response_model=AiKlineDrawingItemSchema)
async def update_ai_item(
    request: AiItemUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AiKlineDrawingItemSchema:
    """单条 AI 画线原位编辑：改锚点（拖拽）与改名（双击），限定本人 AI 画线组。"""
    service = KlineDrawingService(session)
    return await service.update_ai_item(
        current_user.id,
        request.target_type,
        request.target_code,
        request.period,
        request.label,
        anchors=[anchor.model_dump() for anchor in request.anchors] if request.anchors else None,
        new_label=request.new_label,
    )


@router.delete("/ai/item", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_item(
    target_type: str,
    target_code: str,
    period: str,
    label: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """删除单条 AI 画线（Delete 键），限定本人 AI 画线组。"""
    service = KlineDrawingService(session)
    await service.delete_ai_item(current_user.id, target_type, target_code, period, label)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
