"""管理后台代理服务器配置 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.proxy_config import (
    ProxyConfigCreate,
    ProxyConfigResponse,
    ProxyConfigTestResponse,
    ProxyConfigUpdate,
)
from app.services.admin.proxy_config_service import ProxyConfigService

router = APIRouter(
    prefix="/proxy-configs",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("", response_model=list[ProxyConfigResponse])
async def list_proxy_configs(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProxyConfigResponse]:
    """列出全部代理服务器配置。"""
    return await ProxyConfigService(session).list_configs()


@router.post(
    "", response_model=ProxyConfigResponse, status_code=status.HTTP_201_CREATED
)
async def create_proxy_config(
    data: ProxyConfigCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProxyConfigResponse:
    """创建新的代理服务器配置。"""
    return await ProxyConfigService(session).create_config(data)


@router.get("/{config_id}", response_model=ProxyConfigResponse)
async def get_proxy_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProxyConfigResponse:
    """获取单条代理服务器配置。"""
    return await ProxyConfigService(session).get_config(config_id)


@router.put("/{config_id}", response_model=ProxyConfigResponse)
async def update_proxy_config(
    config_id: int,
    data: ProxyConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProxyConfigResponse:
    """更新代理服务器配置。"""
    return await ProxyConfigService(session).update_config(config_id, data)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除代理服务器配置（引用渠道自动解绑）。"""
    await ProxyConfigService(session).delete_config(config_id)


@router.post("/{config_id}/test", response_model=ProxyConfigTestResponse)
async def test_proxy_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProxyConfigTestResponse:
    """测试代理服务器连通性。"""
    return await ProxyConfigService(session).test_config(config_id)
