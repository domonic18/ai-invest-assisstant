"""管理后台 LLM 配置 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestResponse,
    LLMConfigUpdate,
)
from app.services.admin.llm_config_service import LLMConfigService

router = APIRouter(
    prefix="/llm-configs",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("", response_model=list[LLMConfigResponse])
async def list_llm_configs(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[LLMConfigResponse]:
    """列出全部 LLM 配置。"""
    return await LLMConfigService(session).list_configs()


@router.post("", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    data: LLMConfigCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigResponse:
    """创建新的 LLM 配置。"""
    try:
        return await LLMConfigService(session).create_config(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{config_id}", response_model=LLMConfigResponse)
async def get_llm_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigResponse:
    """获取单条 LLM 配置。"""
    config = await LLMConfigService(session).get_config(config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM config not found")
    return config


@router.put("/{config_id}", response_model=LLMConfigResponse)
async def update_llm_config(
    config_id: int,
    data: LLMConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigResponse:
    """更新 LLM 配置。"""
    result = await LLMConfigService(session).update_config(config_id, data)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM config not found")
    return result


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除 LLM 配置。"""
    try:
        await LLMConfigService(session).delete_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{config_id}/set-default", response_model=LLMConfigResponse)
async def set_default_llm_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigResponse:
    """将某条 LLM 配置设为全局默认。"""
    try:
        return await LLMConfigService(session).set_default_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{config_id}/test", response_model=LLMConfigTestResponse)
async def test_llm_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigTestResponse:
    """测试 LLM 配置的连通性。"""
    try:
        return await LLMConfigService(session).test_config_connection(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
