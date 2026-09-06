"""UserService 注册/认证/用户设置契约测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.auth import RegisterRequest
from app.schemas.user import MovingAverageConfig, UserSettings, UserSettingsUpdate
from app.services.user.user_service import DEFAULT_MA_CONFIGS, UserService


@pytest.mark.unit
class TestUserService:
    @pytest.mark.asyncio
    async def test_create_user_hashes_password(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.scalar = AsyncMock(return_value=1)
        data = RegisterRequest(username="tester", email="test@example.com", password="secret123")

        user = await UserService(session).create_user(data)

        assert user.username == "tester"
        assert user.email == "test@example.com"
        assert user.password_hash != "secret123"
        assert user.role == "user"
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_always_regular_role(self) -> None:
        """注册一律 user 角色；管理员经 bootstrap_admin 显式提权（防开放注册抢占）。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.scalar = AsyncMock(return_value=0)
        data = RegisterRequest(username="admin", email="admin@example.com", password="secret123")

        user = await UserService(session).create_user(data)

        assert user.role == "user"
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subsequent_user_is_regular_user(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.scalar = AsyncMock(return_value=5)
        data = RegisterRequest(username="user", email="user@example.com", password="secret123")

        user = await UserService(session).create_user(data)

        assert user.role == "user"
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self) -> None:
        from app.core.security import get_password_hash

        session = MagicMock()
        user = MagicMock()
        user.password_hash = get_password_hash("secret123")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        )

        result = await UserService(session).authenticate_user("tester", "secret123")

        assert result is user

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self) -> None:
        from app.core.security import get_password_hash

        session = MagicMock()
        user = MagicMock()
        user.password_hash = get_password_hash("secret123")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        )

        result = await UserService(session).authenticate_user("tester", "wrong")

        assert result is None

    @pytest.mark.asyncio
    async def test_attempt_login_locked_raises_429(self) -> None:
        from app.core.exceptions import LoginLockedError

        session = MagicMock()
        with (
            patch("app.core.login_throttle.locked_seconds", AsyncMock(return_value=600)),
            patch("app.core.login_throttle.record_failure", AsyncMock()) as record,
        ):
            with pytest.raises(LoginLockedError) as exc_info:
                await UserService(session).attempt_login("tester", "secret123", "1.2.3.4")

        assert exc_info.value.retry_after == 600
        record.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_attempt_login_failure_records_and_audits(self) -> None:
        from app.core.exceptions import UnauthorizedError
        from app.core.security import get_password_hash

        session = MagicMock()
        user = MagicMock()
        user.password_hash = get_password_hash("secret123")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        )
        with (
            patch("app.core.login_throttle.locked_seconds", AsyncMock(return_value=0)),
            patch("app.core.login_throttle.record_failure", AsyncMock()) as record,
            patch("app.core.login_throttle.reset_failures", AsyncMock()) as reset,
        ):
            with pytest.raises(UnauthorizedError):
                await UserService(session).attempt_login("tester", "wrong", "1.2.3.4")

        record.assert_awaited_once_with("tester", "1.2.3.4")
        reset.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_attempt_login_success_resets_failures(self) -> None:
        from app.core.security import get_password_hash

        session = MagicMock()
        user = MagicMock()
        user.password_hash = get_password_hash("secret123")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        )
        with (
            patch("app.core.login_throttle.locked_seconds", AsyncMock(return_value=0)),
            patch("app.core.login_throttle.record_failure", AsyncMock()) as record,
            patch("app.core.login_throttle.reset_failures", AsyncMock()) as reset,
        ):
            result = await UserService(session).attempt_login("tester", "secret123", "1.2.3.4")

        assert result is user
        record.assert_not_awaited()
        reset.assert_awaited_once_with("tester", "1.2.3.4")

    @pytest.mark.asyncio
    async def test_get_settings_returns_defaults_when_missing(self) -> None:
        session = MagicMock()
        user = MagicMock()
        user.settings = None

        settings = await UserService(session).get_settings(user)

        assert settings == UserSettings(ma_configs=DEFAULT_MA_CONFIGS)

    @pytest.mark.asyncio
    async def test_get_settings_returns_defaults_for_invalid_json(self) -> None:
        session = MagicMock()
        user = MagicMock()
        user.settings = {"ma_configs": [{"period": -1, "color": "red", "enabled": True}]}

        settings = await UserService(session).get_settings(user)

        assert settings == UserSettings(ma_configs=DEFAULT_MA_CONFIGS)

    @pytest.mark.asyncio
    async def test_update_settings_persists_and_returns_validated_config(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        user = MagicMock()
        user.settings = None
        update = UserSettingsUpdate(
            ma_configs=[MovingAverageConfig(period=5, color="#ff0000", enabled=True)]
        )

        result = await UserService(session).update_settings(user, update)

        assert result.ma_configs[0].period == 5
        assert result.ma_configs[0].color == "#ff0000"
        assert user.settings == result.model_dump()
        session.commit.assert_awaited_once()
