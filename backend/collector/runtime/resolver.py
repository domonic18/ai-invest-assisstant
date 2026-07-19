"""Task-based collector channel resolution.

Channels are resolved through the ``collector_channel_data_types`` association
table: a channel is eligible for a task only if it is enabled **and** has an
association row for the task; ordering follows the admin-configured priority.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from collector.runtime.channels import ChannelConfig


async def list_ordered_channel_configs_for_task(
    session: AsyncSession, task_name: str
) -> list[Any]:
    """Return enabled channel config rows for ``task_name`` ordered by priority."""
    from app.models.collector_channel_config import CollectorChannelConfig
    from app.models.collector_channel_data_type import CollectorChannelDataType

    stmt = (
        select(CollectorChannelConfig)
        .join(
            CollectorChannelDataType,
            CollectorChannelDataType.channel_id == CollectorChannelConfig.id,
        )
        .where(CollectorChannelConfig.is_enabled.is_(True))
        .where(CollectorChannelDataType.data_type == task_name)
        .order_by(CollectorChannelDataType.priority, CollectorChannelConfig.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def resolve_channel_for_task(
    session: AsyncSession,
    task_name: str,
    preferred_source: str | None = None,
) -> ChannelConfig | None:
    """Resolve an enabled channel that supports ``task_name``.

    If ``preferred_source`` is provided and matches an enabled channel that
    supports the task, it is returned. Otherwise the enabled supporting
    channel with the smallest priority value is returned. ``None`` means no
    channel is available.
    """
    rows = await list_ordered_channel_configs_for_task(session, task_name)

    if preferred_source:
        for config in rows:
            if config.source == preferred_source:
                return _to_channel_config(config)

    if rows:
        return _to_channel_config(rows[0])

    return None


async def resolve_channels_for_task(
    session: AsyncSession,
    task_name: str,
    preferred_source: str | None = None,
) -> list[ChannelConfig]:
    """Resolve all enabled channels for ``task_name`` ordered by priority.

    ``preferred_source`` moves the matching channel to the front while keeping
    the remaining candidates as fallbacks.
    """
    rows = await list_ordered_channel_configs_for_task(session, task_name)
    configs = [_to_channel_config(row) for row in rows]
    if preferred_source:
        configs.sort(key=lambda cfg: 0 if cfg.source == preferred_source else 1)
    return configs


async def list_channels_for_task(
    session: AsyncSession, task_name: str
) -> list[dict[str, Any]]:
    """List all enabled channels that support ``task_name``.

    Returned dictionaries are lightweight and suitable for admin UI selectors.
    """
    rows = await list_ordered_channel_configs_for_task(session, task_name)
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
