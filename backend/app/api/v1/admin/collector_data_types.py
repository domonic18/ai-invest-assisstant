"""Admin collector data-type channel priority API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.collector_channel_config import (
    DataTypeChannelPriorityInput,
    DataTypeChannelsResponse,
)
from app.services.collector_channel_config_service import (
    CollectorChannelConfigService,
)

router = APIRouter(
    prefix="/collector/data-types",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("", response_model=list[DataTypeChannelsResponse])
async def list_data_type_channels(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DataTypeChannelsResponse]:
    """按数据类型列出采集渠道及优先级。"""
    service = CollectorChannelConfigService(session)
    return await service.list_data_type_channels()


@router.put("/{data_type}/channels", response_model=DataTypeChannelsResponse)
async def replace_data_type_channels(
    data_type: str,
    items: list[DataTypeChannelPriorityInput],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DataTypeChannelsResponse:
    """整体替换某数据类型的渠道关联（增删与排序）。"""
    service = CollectorChannelConfigService(session)
    try:
        return await service.replace_data_type_channels(data_type, items)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
