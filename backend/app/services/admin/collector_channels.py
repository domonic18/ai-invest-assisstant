"""采集渠道配置服务。"""

from datetime import datetime, timezone
from typing import Any

import structlog
from cryptography.fernet import InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_channel_config import CollectorChannelConfig
from app.models.collector_channel_data_type import CollectorChannelDataType
from app.repositories.admin.collector_channel_config_repository import (
    CollectorChannelConfigRepository,
)
from app.repositories.admin.collector_channel_data_type_repository import (
    CollectorChannelDataTypeRepository,
)
from app.schemas.collector_channel_config import (
    CollectorChannelConfigCreate,
    CollectorChannelConfigResponse,
    CollectorChannelConfigUpdate,
    DataTypeChannelItem,
    DataTypeChannelPriorityInput,
    DataTypeChannelsResponse,
)
from app.utils.crypto import decrypt_token, encrypt_token, mask_token

logger = structlog.get_logger()


class CollectorChannelConfigService:
    """面向管理后台的采集渠道配置服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CollectorChannelConfigRepository(session)
        self.data_type_repo = CollectorChannelDataTypeRepository(session)

    async def list_configs(self) -> list[CollectorChannelConfigResponse]:
        """按来源排序列出全部渠道配置。"""
        rows = await self.repo.list_ordered()
        return [self._to_response(row) for row in rows]

    async def get_config(self, config_id: int) -> CollectorChannelConfigResponse | None:
        """按 ID 查询渠道配置。"""
        config = await self.repo.get(config_id)
        if not config:
            return None
        return self._to_response(config)

    async def create_config(
        self, data: CollectorChannelConfigCreate
    ) -> CollectorChannelConfigResponse:
        """创建新的渠道配置。"""
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
        self.repo.add(config)
        await self.session.flush()
        await self._sync_associations_from_jsonb(config)
        await self.session.commit()
        await self.repo.refresh(config)
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
        """更新已有渠道配置。"""
        config = await self.repo.get(config_id)
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
            await self._sync_associations_from_jsonb(config)
        if data.extra is not None:
            config.extra = data.extra
        if data.api_key:
            config.api_key_encrypted = encrypt_token(data.api_key)

        config.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.repo.refresh(config)
        return self._to_response(config)

    async def delete_config(self, config_id: int) -> None:
        """删除渠道配置。"""
        config = await self.repo.get(config_id)
        if not config:
            raise ValueError(f"Collector channel config {config_id} not found")
        await self.repo.delete(config)
        await self.session.commit()

    async def get_enabled_config(self, source: str) -> CollectorChannelConfig | None:
        """返回某来源已启用的配置（如存在）。"""
        return await self.repo.get_enabled_by_source(source)

    async def list_data_type_channels(self) -> list[DataTypeChannelsResponse]:
        """按数据类型列出渠道及优先级（priority 升序）。

        数据类型全集 = 采集任务注册表 TASK_MAP 的键 ∪ 关联表已有类型。
        """
        from collector.runtime.registry import TASK_MAP

        known_types = set(TASK_MAP) | await self.data_type_repo.get_distinct_data_types()
        associations = await self.data_type_repo.list_all()
        grouped: dict[str, list[DataTypeChannelItem]] = {dt: [] for dt in known_types}
        for assoc in associations:
            channel = assoc.channel
            grouped.setdefault(assoc.data_type, []).append(
                DataTypeChannelItem(
                    channel_id=assoc.channel_id,
                    source=channel.source,
                    name=channel.name,
                    is_enabled=channel.is_enabled,
                    priority=assoc.priority,
                )
            )
        return [
            DataTypeChannelsResponse(data_type=dt, channels=grouped[dt])
            for dt in sorted(grouped)
        ]

    async def replace_data_type_channels(
        self, data_type: str, items: list[DataTypeChannelPriorityInput]
    ) -> DataTypeChannelsResponse:
        """整体替换某数据类型的渠道关联（增删与排序一次完成）。

        Raises:
            ValueError: data_type 不是已知的采集任务类型。
            LookupError: 存在不合法的 channel_id。
        """
        from collector.runtime.registry import TASK_MAP

        known_types = set(TASK_MAP) | await self.data_type_repo.get_distinct_data_types()
        if data_type not in known_types:
            raise ValueError(f"未知的数据类型: {data_type}")

        channel_ids = {item.channel_id for item in items}
        channels: dict[int, CollectorChannelConfig] = {}
        for channel_id in channel_ids:
            channel = await self.repo.get(channel_id)
            if channel is None:
                raise LookupError(f"渠道配置不存在: {channel_id}")
            channels[channel_id] = channel

        affected_channel_ids = {
            assoc.channel_id
            for assoc in await self.data_type_repo.list_for_data_type(data_type)
        } | channel_ids

        await self.data_type_repo.delete_for_data_type(data_type)
        ordered = sorted(items, key=lambda item: item.priority)
        for index, item in enumerate(ordered, start=1):
            self.session.add(
                CollectorChannelDataType(
                    channel_id=item.channel_id,
                    data_type=data_type,
                    priority=index,
                )
            )
        await self.session.flush()
        await self._resync_jsonb_for_channels(affected_channel_ids)
        await self.session.commit()
        logger.info(
            "collector_data_type_channels_replaced",
            data_type=data_type,
            channel_ids=[item.channel_id for item in ordered],
        )
        return await self._get_data_type_channels(data_type)

    async def _get_data_type_channels(
        self, data_type: str
    ) -> DataTypeChannelsResponse:
        associations = await self.data_type_repo.list_for_data_type(data_type)
        return DataTypeChannelsResponse(
            data_type=data_type,
            channels=[
                DataTypeChannelItem(
                    channel_id=assoc.channel_id,
                    source=assoc.channel.source,
                    name=assoc.channel.name,
                    is_enabled=assoc.channel.is_enabled,
                    priority=assoc.priority,
                )
                for assoc in associations
            ],
        )

    async def _sync_associations_from_jsonb(
        self, channel: CollectorChannelConfig
    ) -> None:
        """渠道 CRUD 修改 supported_data_types 后同步关联表。

        已有关联行的 priority 保持不变；新增类型追加到该类型优先级末尾；
        被移除的类型删除关联行。
        """
        desired = set(channel.supported_data_types or [])
        existing = await self.data_type_repo.list_for_channel(channel.id)
        existing_types = {assoc.data_type for assoc in existing}
        for assoc in existing:
            if assoc.data_type not in desired:
                await self.session.delete(assoc)
        for data_type in sorted(desired - existing_types):
            max_priority = await self.data_type_repo.max_priority(data_type)
            self.session.add(
                CollectorChannelDataType(
                    channel_id=channel.id,
                    data_type=data_type,
                    priority=max_priority + 1,
                )
            )
        await self.session.flush()

    async def _resync_jsonb_for_channels(self, channel_ids: set[int]) -> None:
        """用关联表重写每个渠道的 supported_data_types 冗余缓存。"""
        for channel_id in channel_ids:
            channel = await self.repo.get(channel_id)
            if channel is None:
                continue
            associations = await self.data_type_repo.list_for_channel(channel_id)
            channel.supported_data_types = sorted(
                assoc.data_type for assoc in associations
            )
        await self.session.flush()

    def _to_response(self, config: CollectorChannelConfig) -> CollectorChannelConfigResponse:
        api_key_masked: str | None = None
        if config.api_key_encrypted:
            try:
                api_key_masked = mask_token(decrypt_token(config.api_key_encrypted))
            except InvalidToken:
                logger.warning(
                    "collector_channel_decryption_failed",
                    config_id=config.id,
                    source=config.source,
                    message="Stored API key cannot be decrypted with current key",
                )
                api_key_masked = "[无法解密]"
        return CollectorChannelConfigResponse(
            id=config.id,
            source=config.source,
            name=config.name,
            base_url=config.base_url,
            api_key_masked=api_key_masked,
            is_enabled=config.is_enabled,
            supported_data_types=config.supported_data_types or [],
            extra=config.extra or {},
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


async def resolve_collector_channel(
    session: AsyncSession, source: str
) -> dict[str, Any] | None:
    """解析某来源已启用的采集渠道配置。

    存在已启用配置时返回包含 ``base_url``、``api_key`` 与 ``extra`` 的字典，否则返回 ``None``。
    """
    service = CollectorChannelConfigService(session)
    config = await service.get_enabled_config(source)
    if not config:
        return None

    api_key: str | None = None
    if config.api_key_encrypted:
        try:
            api_key = decrypt_token(config.api_key_encrypted)
        except InvalidToken:
            logger.error(
                "collector_channel_resolve_decryption_failed",
                source=config.source,
                config_id=config.id,
                message="Cannot decrypt API key; channel unavailable",
            )
            return None

    return {
        "base_url": config.base_url,
        "api_key": api_key,
        "extra": config.extra or {},
    }
