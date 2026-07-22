"""Collector channel resolution and seeding.

Channels are admin-configurable data sources.  Each collector task picks the
first enabled channel from its candidate list and receives the channel's
``base_url`` / ``api_key`` in its configuration.
"""

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.collector_channel_config_service import resolve_collector_channel

logger = structlog.get_logger()


@dataclass(frozen=True)
class ChannelConfig:
    """Resolved configuration for an enabled collector channel."""

    source: str
    base_url: str | None
    api_key: str | None
    extra: dict[str, Any]


DEFAULT_CHANNELS: list[dict[str, Any]] = [
    {
        "source": "sina",
        "name": "新浪财经",
        "base_url": "https://hq.sinajs.cn",
        "is_enabled": True,
        "supported_data_types": [
            "kline",
            "index-kline",
            "auction",
            "macro",
            "news",
            "quote",
            "stock-list",
            "market-breadth",
            "index-spot",
            "index-minute",
            "stock-minute",
            "etf-kline",
        ],
        "extra": {},
    },
    {
        "source": "eastmoney",
        "name": "东方财富",
        "base_url": None,
        "is_enabled": True,
        "supported_data_types": [
            "fund-flow",
            "sector-fund-flow",
            "dragon-list",
            "research-report",
            "fund-holdings",
            "financial-report",
            "limit-up-pool",
            "broken-pool",
            "limit-down-pool",
            "a50-kline",
        ],
        "extra": {},
    },
    {
        "source": "ths",
        "name": "同花顺",
        "base_url": None,
        "is_enabled": True,
        "supported_data_types": ["kline", "auction", "sector-fund-flow"],
        "extra": {},
    },
    {
        "source": "cninfo",
        "name": "巨潮资讯",
        "base_url": None,
        "is_enabled": True,
        "supported_data_types": ["company-profile", "disclosure", "financial-report", "ipo-info"],
        "extra": {},
    },
    {
        "source": "tushare",
        "name": "Tushare Pro",
        "base_url": "http://api.tushare.pro",
        "is_enabled": True,
        "supported_data_types": ["index-auction"],
        "extra": {},
    },
    {
        "source": "exchange",
        "name": "沪深交易所",
        "base_url": None,
        "is_enabled": True,
        "supported_data_types": ["market-amount"],
        "extra": {},
    },
]


async def seed_default_channels(session: AsyncSession) -> None:
    """Insert default channel rows for any missing sources and merge default
    supported data types into existing default channels.

    This is idempotent: existing rows are updated to include any new default
    data types, but admin-added types and other customizations are preserved.
    """
    from sqlalchemy import select

    from app.models.collector_channel_config import CollectorChannelConfig

    existing = {
        row.source: row
        for row in (
            await session.execute(select(CollectorChannelConfig))
        ).scalars().all()
    }
    inserted = 0
    updated = 0
    for data in DEFAULT_CHANNELS:
        if data["source"] in existing:
            config = existing[data["source"]]
            default_types = set(data.get("supported_data_types", []))
            current_types = set(config.supported_data_types or [])
            merged_types = sorted(current_types | default_types)
            if merged_types != sorted(current_types):
                config.supported_data_types = merged_types
                updated += 1
            continue
        session.add(
            CollectorChannelConfig(
                source=data["source"],
                name=data["name"],
                base_url=data.get("base_url"),
                is_enabled=data.get("is_enabled", True),
                supported_data_types=data.get("supported_data_types", []),
                extra=data.get("extra", {}),
            )
        )
        inserted += 1
    if inserted or updated:
        await session.commit()

    await _seed_data_type_associations(session)

    logger.info(
        "collector_default_channels_seeded", inserted=inserted, updated=updated
    )


async def _seed_data_type_associations(session: AsyncSession) -> None:
    """Seed channel data-type priority rows for default channels.

    priority 取 DEFAULT_CHANNELS 声明序号；已存在的关联行跳过，不覆盖管理员
    在后台自定义的优先级。
    """
    from sqlalchemy import select

    from app.models.collector_channel_config import CollectorChannelConfig
    from app.models.collector_channel_data_type import CollectorChannelDataType

    channels = {
        row.source: row
        for row in (
            await session.execute(select(CollectorChannelConfig))
        ).scalars().all()
    }
    existing_keys = {
        (row.channel_id, row.data_type)
        for row in (
            await session.execute(select(CollectorChannelDataType))
        ).scalars().all()
    }
    added = 0
    for idx, data in enumerate(DEFAULT_CHANNELS, start=1):
        channel = channels.get(data["source"])
        if channel is None:
            continue
        for data_type in data.get("supported_data_types", []):
            if (channel.id, data_type) in existing_keys:
                continue
            session.add(
                CollectorChannelDataType(
                    channel_id=channel.id, data_type=data_type, priority=idx
                )
            )
            added += 1
    if added:
        await session.commit()
    logger.info("collector_channel_data_types_seeded", added=added)


async def get_channel_config(
    session: AsyncSession, sources: list[str]
) -> ChannelConfig | None:
    """Return the first enabled channel config among ``sources``.

    ``sources`` should be ordered by preference.  If none of the listed
    sources is enabled or configured, ``None`` is returned.
    """
    for source in sources:
        resolved = await resolve_collector_channel(session, source)
        if resolved:
            return ChannelConfig(
                source=source,
                base_url=resolved.get("base_url"),
                api_key=resolved.get("api_key"),
                extra=resolved.get("extra") or {},
            )
    return None
