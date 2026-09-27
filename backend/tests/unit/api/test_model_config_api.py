"""模型配置 API 端点契约测试（ASR 渠道自社媒迁入 + llm 路由冒烟）。"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.model_config import AsrConfigResponse, AsrConfigTestResponse

_NOW = datetime(2026, 9, 15, 10, 0, 0)


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """绕过管理员认证并注入 AsyncMock session 的客户端。"""
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


@pytest.mark.unit
class TestAdminAsrConfigEndpoints:
    def _asr_config_response(self) -> AsrConfigResponse:
        return AsrConfigResponse(
            provider="minimax",
            base_url="https://api.minimaxi.com",
            model="asr-1.0",
            api_key_masked="sk-1****abcd",
            api_key_configured=True,
            max_audio_seconds=600,
            hotwords=["美联储"],
            enabled=True,
            updated_at=_NOW,
        )

    def test_get_asr_config_masked(self, admin_client) -> None:
        client, mock_session = admin_client
        config = SimpleNamespace(
            provider="minimax",
            base_url="https://api.minimaxi.com",
            model="asr-1.0",
            api_key_encrypted="enc",
            api_key_masked="sk-1****abcd",
            max_audio_seconds=600,
            hotwords=["美联储"],
            enabled=True,
            updated_at=_NOW,
        )
        with patch(
            "app.services.admin.asr_config_service.get_or_create_config",
            AsyncMock(return_value=config),
        ):
            response = client.get("/api/v1/admin/model-configs/asr")
        assert response.status_code == 200
        data = response.json()
        assert data["apiKeyConfigured"] is True
        assert data["apiKeyMasked"] == "sk-1****abcd"
        assert "apiKey" not in data

    def test_update_asr_config_passes_actor(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_update = AsyncMock(return_value=self._asr_config_response())
        with patch(
            "app.services.admin.asr_config_service.update_config", mock_update
        ):
            response = client.put(
                "/api/v1/admin/model-configs/asr",
                json={"model": "asr-1.0", "apiKey": "sk-new", "enabled": True},
            )
        assert response.status_code == 200
        payload = mock_update.await_args.args[1]
        assert payload.api_key == "sk-new"
        assert mock_update.await_args.kwargs["actor_id"] == 1

    def test_test_asr_config_passes_actor(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_test = AsyncMock(
            return_value=AsrConfigTestResponse(
                ok=True, latency_ms=123, text="样例", error=None
            )
        )
        with patch(
            "app.services.admin.asr_config_service.test_connection", mock_test
        ):
            response = client.post("/api/v1/admin/model-configs/asr/test")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert mock_test.await_args.kwargs["actor_id"] == 1


@pytest.mark.unit
class TestLLMConfigRoutes:
    def test_list_llm_configs(self, admin_client) -> None:
        """/llm 与 /asr 同挂 model-configs 前缀的路由冒烟（防路径参数吞并）。"""
        client, mock_session = admin_client
        with patch(
            "app.api.v1.admin.model_config.LLMConfigService"
        ) as service_cls:
            service_cls.return_value.list_configs = AsyncMock(return_value=[])
            response = client.get("/api/v1/admin/model-configs/llm")
        assert response.status_code == 200
        assert response.json() == []
        service_cls.return_value.list_configs.assert_awaited_once()
