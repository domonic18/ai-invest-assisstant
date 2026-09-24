"""签名服务配置测试：默认值安全、env 前缀覆盖、非法值拒绝。"""

import pytest
from pydantic import ValidationError

from app.signer.settings import SignerSettings

pytestmark = pytest.mark.unit


class TestDefaults:
    def test_safe_defaults(self) -> None:
        settings = SignerSettings()
        assert settings.bind_port == 8010
        assert settings.warm_slots == 2
        assert settings.warm_refresh_seconds == 1800.0
        assert settings.sign_timeout_seconds == 8.0
        assert settings.sdk_ready_timeout_seconds == 25.0
        assert settings.sign_attempts_per_request == 2
        assert settings.headless is True
        assert settings.signing_page_url == "https://www.douyin.com/"


class TestEnvOverride:
    def test_env_prefix_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DOUYIN_SIGNER_BIND_PORT", "9000")
        monkeypatch.setenv("DOUYIN_SIGNER_WARM_SLOTS", "3")
        monkeypatch.setenv("DOUYIN_SIGNER_HEADLESS", "false")
        settings = SignerSettings()
        assert settings.bind_port == 9000
        assert settings.warm_slots == 3
        assert settings.headless is False

    def test_other_env_prefix_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIGNER_BIND_PORT", "9000")
        assert SignerSettings().bind_port == 8010


class TestValidation:
    @pytest.mark.parametrize(
        "field",
        [
            "warm_slots",
            "warm_refresh_seconds",
            "max_concurrent_signs",
            "sign_timeout_seconds",
            "context_open_timeout_seconds",
            "sdk_ready_timeout_seconds",
        ],
    )
    def test_non_positive_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            SignerSettings(**{field: 0})

    def test_attempts_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SignerSettings(sign_attempts_per_request=5)
