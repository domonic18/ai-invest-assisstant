"""管理后台模型配置 API 端点：LLM 条目（chat/vision/embedding）+ ASR 渠道统一入口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.models.user import User
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestResponse,
    LLMConfigUpdate,
)
from app.schemas.model_config import (
    AsrConfigResponse,
    AsrConfigTestResponse,
    AsrConfigUpdateRequest,
)
from app.services.admin import asr_config_service
from app.services.admin.llm_config_service import LLMConfigService

router = APIRouter(
    prefix="/model-configs",
    dependencies=[Depends(get_current_admin_user)],
)

llm_router = APIRouter(prefix="/llm")


@llm_router.get("", response_model=list[LLMConfigResponse])
async def list_llm_configs(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[LLMConfigResponse]:
    """列出全部 LLM 配置。"""
    return await LLMConfigService(session).list_configs()


@llm_router.post("", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    data: LLMConfigCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigResponse:
    """创建新的 LLM 配置。"""
    return await LLMConfigService(session).create_config(data)


@llm_router.get("/{config_id}", response_model=LLMConfigResponse)
async def get_llm_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigResponse:
    """获取单条 LLM 配置。"""
    return await LLMConfigService(session).get_config(config_id)


@llm_router.put("/{config_id}", response_model=LLMConfigResponse)
async def update_llm_config(
    config_id: int,
    data: LLMConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigResponse:
    """更新 LLM 配置。"""
    return await LLMConfigService(session).update_config(config_id, data)


@llm_router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除 LLM 配置。"""
    await LLMConfigService(session).delete_config(config_id)


@llm_router.post("/{config_id}/set-default", response_model=LLMConfigResponse)
async def set_default_llm_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigResponse:
    """将某条 LLM 配置设为全局默认。"""
    return await LLMConfigService(session).set_default_config(config_id)


@llm_router.post("/{config_id}/test", response_model=LLMConfigTestResponse)
async def test_llm_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigTestResponse:
    """测试 LLM 配置的连通性。"""
    return await LLMConfigService(session).test_config_connection(config_id)


@router.get("/asr", response_model=AsrConfigResponse)
async def get_asr_config(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AsrConfigResponse:
    """ASR 配置 masked 视图（密钥只回脱敏串）。"""
    config = await asr_config_service.get_or_create_config(session)
    return asr_config_service.to_response(config)


@router.put("/asr", response_model=AsrConfigResponse)
async def update_asr_config(
    payload: AsrConfigUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> AsrConfigResponse:
    """更新 ASR 配置（apiKey write-only：留空不换，写审计）。"""
    return await asr_config_service.update_config(session, payload, actor_id=admin.id)


@router.post("/asr/test", response_model=AsrConfigTestResponse)
async def test_asr_config(
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> AsrConfigTestResponse:
    """连接测试：内置样例音频实调转写接口（不抛异常，失败给原因）。"""
    return await asr_config_service.test_connection(session, actor_id=admin.id)


# /asr 系列必须先于 /llm/{config_id} 注册，否则 "asr" 会命中 int 路径参数直接 422
router.include_router(llm_router)
