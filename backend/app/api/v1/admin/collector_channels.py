"""Admin collector channel configuration API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.models.collector_channel_config import CollectorChannelConfig
from app.schemas.collector_channel_config import (
    CollectorChannelConfigCreate,
    CollectorChannelConfigResponse,
    CollectorChannelConfigUpdate,
)
from app.services.collector_channel_config_service import (
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
    """List all collector channel configurations."""
    service = CollectorChannelConfigService(session)
    return await service.list_configs()


@router.post("", response_model=CollectorChannelConfigResponse)
async def create_collector_channel_config(
    data: CollectorChannelConfigCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorChannelConfigResponse:
    """Create a new collector channel configuration."""
    service = CollectorChannelConfigService(session)
    return await service.create_config(data)


@router.get("/{config_id}", response_model=CollectorChannelConfigResponse)
async def get_collector_channel_config(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorChannelConfigResponse:
    """Get a single collector channel configuration."""
    service = CollectorChannelConfigService(session)
    config = await session.get(CollectorChannelConfig, config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collector channel config not found",
        )
    return service._to_response(config)


@router.put("/{config_id}", response_model=CollectorChannelConfigResponse)
async def update_collector_channel_config(
    config_id: int,
    data: CollectorChannelConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorChannelConfigResponse:
    """Update an existing collector channel configuration."""
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
    """Delete a collector channel configuration."""
    service = CollectorChannelConfigService(session)
    try:
        await service.delete_config(config_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
