"""管理后台采集渠道配置 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.collector_channel_config import (
    CollectorChannelConfigCreate,
    CollectorChannelConfigResponse,
    CollectorChannelConfigUpdate,
)
from app.services.admin.collector_channels import (
    CollectorChannelConfigService,
)

router = APIRouter(
    prefix="/collector/channels",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("", response_model=list[CollectorChannelConfigResponse])
async def list_collector_channel_configs(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CollectorChannelConfigResponse]:
    """列出全部采集渠道配置。"""
    service = CollectorChannelConfigService(session)
    return await service.list_configs()


@router.post("", response_model=CollectorChannelConfigResponse)
async def create_collector_channel_config(
    data: CollectorChannelConfigCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorChannelConfigResponse:
    """创建新的采集渠道配置。"""
    service = CollectorChannelConfigService(session)
    return await service.create_config(data)


@router.get("/{config_id}", response_model=CollectorChannelConfigResponse)
async def get_collector_channel_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorChannelConfigResponse:
    """获取单条采集渠道配置。"""
    service = CollectorChannelConfigService(session)
    config = await service.get_config(config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collector channel config not found",
        )
    return config


@router.put("/{config_id}", response_model=CollectorChannelConfigResponse)
async def update_collector_channel_config(
    config_id: int,
    data: CollectorChannelConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorChannelConfigResponse:
    """更新已有采集渠道配置。"""
    service = CollectorChannelConfigService(session)
    updated = await service.update_config(config_id, data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collector channel config not found",
        )
    return updated


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collector_channel_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除采集渠道配置。"""
    service = CollectorChannelConfigService(session)
    try:
        await service.delete_config(config_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
