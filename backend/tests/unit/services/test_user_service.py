from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.auth import RegisterRequest
from app.services.user_service import UserService


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
    async def test_first_user_becomes_admin(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.scalar = AsyncMock(return_value=0)
        data = RegisterRequest(username="admin", email="admin@example.com", password="secret123")

        user = await UserService(session).create_user(data)

        assert user.role == "admin"
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
