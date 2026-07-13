"""Collector channel configuration service."""

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_channel_config import CollectorChannelConfig
from app.schemas.collector_channel_config import (
    CollectorChannelConfigCreate,
    CollectorChannelConfigResponse,
    CollectorChannelConfigUpdate,
)
from app.utils.crypto import decrypt_token, encrypt_token, mask_token

logger = structlog.get_logger()


class CollectorChannelConfigService:
    """Admin-facing collector channel configuration service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_configs(self) -> list[CollectorChannelConfigResponse]:
        """List all channel configurations ordered by source."""
        stmt = select(CollectorChannelConfig).order_by(CollectorChannelConfig.source)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_response(row) for row in rows]

    async def create_config(
        self, data: CollectorChannelConfigCreate
    ) -> CollectorChannelConfigResponse:
        """Create a new channel configuration."""
        config = CollectorChannelConfig(
            source=data.source,
            name=data.name,
            base_url=data.base_url,
            api_key_encrypted=(
                encrypt_token(data.api_key) if data.api_key else None
            ),
            is_enabled=data.is_enabled,
            supported_data_types=data.supported_data_types,
            extra=data.extra,
        )
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        logger.info(
            "collector_channel_config_created",
            config_id=config.id,
            source=config.source,
            is_enabled=config.is_enabled,
        )
        return self._to_response(config)

    async def update_config(
        self, config_id: int, data: CollectorChannelConfigUpdate
    ) -> CollectorChannelConfigResponse | None:
        """Update an existing channel configuration."""
        config = await self.session.get(CollectorChannelConfig, config_id)
        if not config:
            return None

        if data.name is not None:
            config.name = data.name
        if data.base_url is not None:
            config.base_url = data.base_url
        if data.is_enabled is not None:
            config.is_enabled = data.is_enabled
        if data.supported_data_types is not None:
            config.supported_data_types = data.supported_data_types
        if data.extra is not None:
            config.extra = data.extra
        if data.api_key:
            config.api_key_encrypted = encrypt_token(data.api_key)

        config.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(config)
        return self._to_response(config)

    async def delete_config(self, config_id: int) -> None:
        """Delete a channel configuration."""
        config = await self.session.get(CollectorChannelConfig, config_id)
        if not config:
            raise ValueError(f"Collector channel config {config_id} not found")
        await self.session.delete(config)
        await self.session.flush()

    async def get_enabled_config(self, source: str) -> CollectorChannelConfig | None:
        """Return the enabled configuration for a source, if any."""
        stmt = select(CollectorChannelConfig).where(
            CollectorChannelConfig.source == source,
            CollectorChannelConfig.is_enabled.is_(True),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def _to_response(self, config: CollectorChannelConfig) -> CollectorChannelConfigResponse:
        return CollectorChannelConfigResponse(
            id=config.id,
            source=config.source,
            name=config.name,
            base_url=config.base_url,
            api_key_masked=(
                mask_token(decrypt_token(config.api_key_encrypted))
                if config.api_key_encrypted
                else None
            ),
            is_enabled=config.is_enabled,
            supported_data_types=config.supported_data_types or [],
            extra=config.extra or {},
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


async def resolve_collector_channel(
    session: AsyncSession, source: str
) -> dict[str, Any] | None:
    """Resolve an enabled collector channel configuration for a source.

    Returns a dictionary with ``base_url``, ``api_key`` and ``extra`` when an
    enabled config exists, otherwise ``None``.
    """
    service = CollectorChannelConfigService(session)
    config = await service.get_enabled_config(source)
    if not config:
        return None
    return {
        "base_url": config.base_url,
        "api_key": (
            decrypt_token(config.api_key_encrypted)
            if config.api_key_encrypted
            else None
        ),
        "extra": config.extra or {},
    }
