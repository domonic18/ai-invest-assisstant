"""后台采集数据类型渠道优先级 API 契约测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.collector_channel_config import (
    DataTypeChannelItem,
    DataTypeChannelsResponse,
)


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """返回带管理员鉴权的 client 与 mock 数据库会话。"""
    mock_session = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.role = "admin"

    async def _override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_admin_user] = lambda: mock_user
    yield client, mock_session
    app.dependency_overrides.clear()


def _response(data_type: str, channels: list[tuple[int, str, int]]) -> DataTypeChannelsResponse:
    return DataTypeChannelsResponse(
        data_type=data_type,
        channels=[
            DataTypeChannelItem(
                channel_id=cid, source=source, name=source, is_enabled=True, priority=p
            )
            for cid, source, p in channels
        ],
    )


@pytest.mark.unit
class TestAdminCollectorDataTypes:
    @patch("app.api.v1.admin.collector_data_types.CollectorChannelConfigService")
    def test_list_data_type_channels(
        self,
        mock_service_cls: MagicMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        service = mock_service_cls.return_value
        service.list_data_type_channels = AsyncMock(
            return_value=[
                _response("kline", [(1, "sina", 1), (3, "ths", 2)]),
                _response("auction", [(1, "sina", 1)]),
            ]
        )
        client, _ = admin_client

        response = client.get("/api/v1/admin/collector/data-types")

        assert response.status_code == 200
        data = response.json()
        assert data[0]["data_type"] == "kline"
        assert [ch["source"] for ch in data[0]["channels"]] == ["sina", "ths"]

    @patch("app.api.v1.admin.collector_data_types.CollectorChannelConfigService")
    def test_replace_data_type_channels(
        self,
        mock_service_cls: MagicMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        service = mock_service_cls.return_value
        service.replace_data_type_channels = AsyncMock(
            return_value=_response("kline", [(3, "ths", 1), (1, "sina", 2)])
        )
        client, _ = admin_client

        response = client.put(
            "/api/v1/admin/collector/data-types/kline/channels",
            json=[
                {"channel_id": 3, "priority": 1},
                {"channel_id": 1, "priority": 2},
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert [ch["source"] for ch in data["channels"]] == ["ths", "sina"]
        service.replace_data_type_channels.assert_awaited_once()

    @patch("app.api.v1.admin.collector_data_types.CollectorChannelConfigService")
    def test_replace_unknown_data_type_returns_400(
        self,
        mock_service_cls: MagicMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        service = mock_service_cls.return_value
        service.replace_data_type_channels = AsyncMock(
            side_effect=ValueError("未知的数据类型: bad-type")
        )
        client, _ = admin_client

        response = client.put(
            "/api/v1/admin/collector/data-types/bad-type/channels",
            json=[{"channel_id": 1, "priority": 1}],
        )

        assert response.status_code == 400

    @patch("app.api.v1.admin.collector_data_types.CollectorChannelConfigService")
    def test_replace_missing_channel_returns_404(
        self,
        mock_service_cls: MagicMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        service = mock_service_cls.return_value
        service.replace_data_type_channels = AsyncMock(
            side_effect=LookupError("渠道配置不存在: 99")
        )
        client, _ = admin_client

        response = client.put(
            "/api/v1/admin/collector/data-types/kline/channels",
            json=[{"channel_id": 99, "priority": 1}],
        )

        assert response.status_code == 404
