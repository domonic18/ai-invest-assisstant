"""采集渠道解析与种子数据。

渠道是管理端可配置的数据源。每个采集任务从候选列表中选取第一个已启用的
渠道，并在配置中拿到该渠道的 ``base_url`` / ``api_key``。
"""

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin.collector_channels import resolve_collector_channel

logger = structlog.get_logger()


@dataclass(frozen=True)
class ChannelConfig:
    """已启用采集渠道的解析结果配置。"""

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
        "supported_data_types": ["kline", "auction", "sector-fund-flow", "concept-constituents"],
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
    """为缺失的 source 插入默认渠道行，并把默认支持的数据类型合并进已有的
    默认渠道。

    本操作幂等：已有行会更新以纳入新增的默认数据类型，但管理员添加的类型
    及其他自定义配置会保留。
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
    """为默认渠道播种渠道-数据类型优先级行。

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
    """返回 ``sources`` 中第一个已启用的渠道配置。

    ``sources`` 应按偏好排序。若列表中的 source 都未启用或未配置，返回
    ``None``。
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
