"""基于任务的采集渠道解析。

渠道通过 ``collector_channel_data_type`` 关联表解析：渠道只有处于启用状态
**且**拥有该任务的关联行才有资格；排序遵循管理端配置的优先级。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from collector.runtime.channels import ChannelConfig


async def list_ordered_channel_configs_for_task(
    session: AsyncSession, task_name: str
) -> list[Any]:
    """返回支持 ``task_name`` 的已启用渠道配置行，按优先级排序。"""
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
    """解析一个支持 ``task_name`` 的已启用渠道。

    若提供 ``preferred_source`` 且匹配到支持该任务的已启用渠道，则返回它；
    否则返回 priority 值最小的已启用支持渠道。返回 ``None`` 表示没有可用
    渠道。
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
    """解析 ``task_name`` 的全部已启用渠道，按优先级排序。

    ``preferred_source`` 把匹配的渠道移到最前，其余候选保持作为 fallback。
    """
    rows = await list_ordered_channel_configs_for_task(session, task_name)
    configs = [_to_channel_config(row) for row in rows]
    if preferred_source:
        configs.sort(key=lambda cfg: 0 if cfg.source == preferred_source else 1)
    return configs


async def list_channels_for_task(
    session: AsyncSession, task_name: str
) -> list[dict[str, Any]]:
    """列出支持 ``task_name`` 的全部已启用渠道。

    返回的字典为轻量结构，适合管理端 UI 的选择器。
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
