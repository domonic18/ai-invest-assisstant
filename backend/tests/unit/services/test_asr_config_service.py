"""ASR 渠道配置服务单测：masked 视图 / write-only 密钥 / 连接测试。"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.social import AsrChannelConfig
from app.schemas.social import AsrConfigUpdateRequest
from app.services.social import asr_config_service


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        provider="minimax",
        base_url="https://api.minimaxi.com",
        model="asr-1.0",
        api_key_encrypted="gAAAA-cipher",
        api_key_masked="sk-1****abcd",
        hotwords=["美联储", "北向资金"],
        max_audio_seconds=600,
        enabled=True,
        updated_by=1,
        updated_at=datetime(2026, 9, 15, 10, 0, 0),
    )


@pytest.mark.unit
class TestGetOrCreateConfig:
    async def test_existing_row_returned_without_insert(self) -> None:
        session = _session()
        existing = AsrChannelConfig(id=1)
        session.get = AsyncMock(return_value=existing)
        result = await asr_config_service.get_or_create_config(session)
        assert result is existing
        session.add.assert_not_called()

    async def test_missing_row_creates_default(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=None)
        result = await asr_config_service.get_or_create_config(session)
        assert isinstance(result, AsrChannelConfig)
        assert result.id == 1
        session.add.assert_called_once()


@pytest.mark.unit
class TestToResponse:
    def test_masked_view(self) -> None:
        response = asr_config_service.to_response(_config())
        assert response.api_key_configured is True
        assert response.api_key_masked == "sk-1****abcd"
        assert response.model == "asr-1.0"
        assert response.hotwords == ["美联储", "北向资金"]
        assert response.enabled is True

    def test_unconfigured_key(self) -> None:
        config = _config()
        config.api_key_encrypted = None
        config.api_key_masked = None
        response = asr_config_service.to_response(config)
        assert response.api_key_configured is False
        assert response.api_key_masked is None


@pytest.mark.unit
class TestUpdateConfig:
    async def test_key_provided_swaps_and_audits(self) -> None:
        session = _session()
        config = _config()
        with (
            patch.object(
                asr_config_service,
                "get_or_create_config",
                AsyncMock(return_value=config),
            ),
            patch.object(
                asr_config_service, "encrypt_token", return_value="ENC::sk-new"
            ),
            patch.object(asr_config_service, "mask_token", return_value="sk-n****w"),
            patch.object(asr_config_service, "record_audit", AsyncMock()) as mock_audit,
        ):
            payload = AsrConfigUpdateRequest(apiKey="sk-new", enabled=False)
            response = await asr_config_service.update_config(
                session, payload, actor_id=7
            )

        assert config.api_key_encrypted == "ENC::sk-new"
        assert config.api_key_masked == "sk-n****w"
        assert config.enabled is False
        assert config.updated_by == 7
        assert response.api_key_configured is True
        assert response.api_key_masked == "sk-n****w"
        kwargs = mock_audit.await_args.kwargs
        assert kwargs["actor_id"] == 7
        assert kwargs["action"] == "social.asr_config.update"
        assert kwargs["detail"]["apiKeyChanged"] is True

    async def test_key_absent_keeps_original(self) -> None:
        session = _session()
        config = _config()
        with (
            patch.object(
                asr_config_service,
                "get_or_create_config",
                AsyncMock(return_value=config),
            ),
            patch.object(asr_config_service, "encrypt_token", AsyncMock()) as mock_enc,
            patch.object(asr_config_service, "record_audit", AsyncMock()) as mock_audit,
        ):
            payload = AsrConfigUpdateRequest(model="asr-2.0")
            await asr_config_service.update_config(session, payload, actor_id=7)

        assert config.model == "asr-2.0"
        assert config.api_key_encrypted == "gAAAA-cipher"
        mock_enc.assert_not_called()
        assert mock_audit.await_args.kwargs["detail"]["apiKeyChanged"] is False

    async def test_key_empty_string_keeps_original(self) -> None:
        session = _session()
        config = _config()
        with (
            patch.object(
                asr_config_service,
                "get_or_create_config",
                AsyncMock(return_value=config),
            ),
            patch.object(asr_config_service, "encrypt_token", AsyncMock()) as mock_enc,
            patch.object(asr_config_service, "record_audit", AsyncMock()),
        ):
            payload = AsrConfigUpdateRequest(apiKey="")
            await asr_config_service.update_config(session, payload, actor_id=7)

        assert config.api_key_encrypted == "gAAAA-cipher"
        mock_enc.assert_not_called()

    async def test_hotwords_and_base_url_updated(self) -> None:
        session = _session()
        config = _config()
        with (
            patch.object(
                asr_config_service,
                "get_or_create_config",
                AsyncMock(return_value=config),
            ),
            patch.object(asr_config_service, "record_audit", AsyncMock()),
        ):
            payload = AsrConfigUpdateRequest(
                baseUrl="https://api.example.com/",
                hotwords=["降息", "北向资金"],
                maxAudioSeconds=300,
            )
            await asr_config_service.update_config(session, payload, actor_id=7)

        assert config.base_url == "https://api.example.com/"
        assert config.hotwords == ["降息", "北向资金"]
        assert config.max_audio_seconds == 300


@pytest.mark.unit
class TestTestConnection:
    async def test_not_configured_fails_without_raising(self) -> None:
        session = _session()
        config = _config()
        config.api_key_encrypted = None
        with (
            patch.object(
                asr_config_service,
                "get_or_create_config",
                AsyncMock(return_value=config),
            ),
            patch.object(asr_config_service, "record_audit", AsyncMock()) as mock_audit,
        ):
            result = await asr_config_service.test_connection(session, actor_id=1)
        assert result.ok is False
        assert result.error == "API Key 未配置"
        assert result.latency_ms >= 0
        kwargs = mock_audit.await_args.kwargs
        assert kwargs["action"] == "social.asr_config.test"
        assert kwargs["detail"]["ok"] is False

    async def test_success_returns_text_and_latency(self) -> None:
        session = _session()
        config = _config()
        mock_sample = AsyncMock(return_value="样例转写文本")
        with (
            patch.object(
                asr_config_service,
                "get_or_create_config",
                AsyncMock(return_value=config),
            ),
            patch.object(asr_config_service, "record_audit", AsyncMock()),
            patch("app.utils.crypto.decrypt_token", return_value="sk-plain"),
            patch.object(asr_config_service, "_transcribe_sample", mock_sample),
        ):
            result = await asr_config_service.test_connection(session, actor_id=1)
        assert result.ok is True
        assert result.error is None
        assert result.text == "样例转写文本"
        assert result.latency_ms >= 0
        mock_sample.assert_awaited_once_with(config, "sk-plain")

    async def test_empty_text_reported_as_failure(self) -> None:
        session = _session()
        config = _config()
        with (
            patch.object(
                asr_config_service,
                "get_or_create_config",
                AsyncMock(return_value=config),
            ),
            patch.object(asr_config_service, "record_audit", AsyncMock()),
            patch("app.utils.crypto.decrypt_token", return_value="sk-plain"),
            patch.object(
                asr_config_service, "_transcribe_sample", AsyncMock(return_value="")
            ),
        ):
            result = await asr_config_service.test_connection(session, actor_id=1)
        assert result.ok is False
        assert result.error == "接口返回空文本"

    async def test_transcribe_exception_reported_not_raised(self) -> None:
        session = _session()
        config = _config()
        with (
            patch.object(
                asr_config_service,
                "get_or_create_config",
                AsyncMock(return_value=config),
            ),
            patch.object(asr_config_service, "record_audit", AsyncMock()),
            patch("app.utils.crypto.decrypt_token", return_value="sk-plain"),
            patch.object(
                asr_config_service,
                "_transcribe_sample",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            result = await asr_config_service.test_connection(session, actor_id=1)
        assert result.ok is False
        assert "boom" in result.error
