"""Unit tests for collector channel configuration service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.collector_channel_config import (
    CollectorChannelConfigCreate,
    CollectorChannelConfigUpdate,
)
from app.services.collector_channel_config_service import (
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
            "app.services.collector_channel_config_service.CollectorChannelConfig",
            return_value=self._config_mock(),
        ):
            with patch(
                "app.services.collector_channel_config_service.encrypt_token",
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
            "app.services.collector_channel_config_service.mask_token",
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
