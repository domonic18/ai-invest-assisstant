"""采集渠道配置服务契约测试。"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.collector_channel_config import (
    CollectorChannelConfigCreate,
    CollectorChannelConfigUpdate,
    DataTypeChannelPriorityInput,
)
from app.services.admin.collector_channels import (
    CollectorChannelConfigService,
)


@pytest.mark.unit
class TestCollectorChannelConfigService:
    @pytest.fixture
    def service(self):
        session = MagicMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.get = AsyncMock()
        session.add = MagicMock()
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = []
        execute_result.all.return_value = []
        execute_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=execute_result)
        return CollectorChannelConfigService(session), session

    def _config_mock(self, is_enabled: bool = True):
        config = MagicMock()
        config.id = 1
        config.source = "eastmoney"
        config.name = "东方财富"
        config.base_url = "https://example.com"
        config.api_key_encrypted = None
        config.is_enabled = is_enabled
        config.supported_data_types = ["fund-flow"]
        config.extra = {}
        config.created_at = datetime.utcnow()
        config.updated_at = datetime.utcnow()
        return config

    @pytest.mark.asyncio
    async def test_create_config_commits(self, service):
        svc, session = service
        data = CollectorChannelConfigCreate(
            source="eastmoney",
            name="东方财富",
            is_enabled=True,
            supported_data_types=["fund-flow"],
        )
        with patch(
            "app.services.admin.collector_channels.CollectorChannelConfig",
            return_value=self._config_mock(),
        ):
            with patch(
                "app.services.admin.collector_channels.encrypt_token",
                return_value="enc",
            ):
                await svc.create_config(data)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_config_commits_and_disables(self, service):
        svc, session = service
        session.get.return_value = self._config_mock(is_enabled=True)
        data = CollectorChannelConfigUpdate(is_enabled=False)
        with patch(
            "app.services.admin.collector_channels.mask_token",
            return_value="***",
        ):
            result = await svc.update_config(1, data)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once()
        assert result.is_enabled is False

    @pytest.mark.asyncio
    async def test_delete_config_commits(self, service):
        svc, session = service
        session.get.return_value = self._config_mock()
        await svc.delete_config(1)
        session.commit.assert_awaited_once()
        session.delete.assert_awaited_once()


def _assoc_mock(channel_id: int, data_type: str, priority: int, source: str):
    assoc = MagicMock()
    assoc.channel_id = channel_id
    assoc.data_type = data_type
    assoc.priority = priority
    channel = MagicMock()
    channel.source = source
    channel.name = source
    channel.is_enabled = True
    assoc.channel = channel
    return assoc


@pytest.mark.unit
class TestDataTypeChannelPriority:
    @pytest.fixture
    def service(self):
        session = MagicMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.get = AsyncMock()
        session.add = MagicMock()
        svc = CollectorChannelConfigService(session)
        svc.data_type_repo = AsyncMock()
        svc.repo = AsyncMock()
        return svc, session

    @pytest.mark.asyncio
    async def test_list_data_type_channels_sorted(self, service):
        svc, _ = service
        svc.data_type_repo.get_distinct_data_types.return_value = {"kline"}
        svc.data_type_repo.list_all.return_value = [
            _assoc_mock(1, "kline", 1, "sina"),
            _assoc_mock(3, "kline", 2, "ths"),
        ]

        result = await svc.list_data_type_channels()

        by_type = {item.data_type: item for item in result}
        assert [ch.source for ch in by_type["kline"].channels] == ["sina", "ths"]
        # TASK_MAP 中其他任务类型也出现在全集里
        assert "auction" in by_type

    @pytest.mark.asyncio
    async def test_replace_normalizes_priority_and_commits(self, service):
        svc, session = service
        svc.data_type_repo.get_distinct_data_types.return_value = {"kline"}
        svc.data_type_repo.list_for_channel.return_value = []
        svc.data_type_repo.list_for_data_type.side_effect = [
            [_assoc_mock(1, "kline", 1, "sina")],  # affected ids 收集
            [  # _get_data_type_channels 返回替换后结果
                _assoc_mock(3, "kline", 1, "ths"),
                _assoc_mock(1, "kline", 2, "sina"),
            ],
        ]
        channel = MagicMock()
        channel.id = 1
        svc.repo.get.return_value = channel

        items = [
            DataTypeChannelPriorityInput(channel_id=3, priority=5),
            DataTypeChannelPriorityInput(channel_id=1, priority=9),
        ]
        result = await svc.replace_data_type_channels("kline", items)

        added = [call.args[0] for call in session.add.call_args_list]
        assert [(row.channel_id, row.priority) for row in added] == [(3, 1), (1, 2)]
        session.commit.assert_awaited_once()
        assert [ch.source for ch in result.channels] == ["ths", "sina"]

    @pytest.mark.asyncio
    async def test_replace_unknown_data_type_raises(self, service):
        svc, _ = service
        svc.data_type_repo.get_distinct_data_types.return_value = set()

        with pytest.raises(ValueError, match="未知的数据类型"):
            await svc.replace_data_type_channels("not-a-task", [])

    @pytest.mark.asyncio
    async def test_replace_missing_channel_raises(self, service):
        svc, _ = service
        svc.data_type_repo.get_distinct_data_types.return_value = {"kline"}
        svc.repo.get.return_value = None

        with pytest.raises(LookupError, match="渠道配置不存在"):
            await svc.replace_data_type_channels(
                "kline", [DataTypeChannelPriorityInput(channel_id=99, priority=1)]
            )
