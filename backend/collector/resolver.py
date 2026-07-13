"""Task-based collector channel resolution.

This module replaces the hard-coded source priority lists in ``collector/tasks.py``
with a capability-driven resolver: a channel is eligible for a task only if it is
enabled **and** declares the task in ``supported_data_types``.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from collector.channels import ChannelConfig


async def resolve_channel_for_task(
    session: AsyncSession,
    task_name: str,
    preferred_source: str | None = None,
) -> ChannelConfig | None:
    """Resolve an enabled channel that supports ``task_name``.

    If ``preferred_source`` is provided and matches an enabled channel that
    supports the task, it is returned. Otherwise the first enabled supporting
    channel ordered by ``id`` is returned. ``None`` means no channel is available.
    """
    from app.models.collector_channel_config import CollectorChannelConfig

    stmt = (
        select(CollectorChannelConfig)
        .where(CollectorChannelConfig.is_enabled.is_(True))
        .where(CollectorChannelConfig.supported_data_types.contains([task_name]))
        .order_by(CollectorChannelConfig.id)
    )
    rows = (await session.execute(stmt)).scalars().all()

    if preferred_source:
        for config in rows:
            if config.source == preferred_source:
                return _to_channel_config(config)

    if rows:
        return _to_channel_config(rows[0])

    return None


async def list_channels_for_task(
    session: AsyncSession,
    task_name: str,
) -> list[dict[str, Any]]:
    """List all enabled channels that support ``task_name``.

    Returned dictionaries are lightweight and suitable for admin UI selectors.
    """
    from app.models.collector_channel_config import CollectorChannelConfig

    stmt = (
        select(CollectorChannelConfig)
        .where(CollectorChannelConfig.is_enabled.is_(True))
        .where(CollectorChannelConfig.supported_data_types.contains([task_name]))
        .order_by(CollectorChannelConfig.id)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "source": config.source,
            "name": config.name,
            "is_enabled": config.is_enabled,
        }
        for config in rows
    ]


def _to_channel_config(config: Any) -> ChannelConfig:
    from app.utils.crypto import decrypt_token

    return ChannelConfig(
        source=config.source,
        base_url=config.base_url,
        api_key=(
            decrypt_token(config.api_key_encrypted)
            if config.api_key_encrypted
            else None
        ),
        extra=config.extra or {},
    )
