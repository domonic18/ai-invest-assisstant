"""bootstrap_admin 显式提权契约测试。"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cli.bootstrap_admin import promote


@pytest.mark.unit
class TestBootstrapAdmin:
    @pytest.mark.asyncio
    async def test_promote_existing_user_to_admin(self) -> None:
        user = MagicMock()
        user.username = "tester"
        user.role = "user"
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        )
        session.commit = AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield session

        with patch("app.cli.bootstrap_admin.AsyncSessionLocal", fake_session):
            assert await promote("tester") is True

        assert user.role == "admin"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_promote_missing_user_fails(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        @asynccontextmanager
        async def fake_session():
            yield session

        with patch("app.cli.bootstrap_admin.AsyncSessionLocal", fake_session):
            assert await promote("ghost") is False

    @pytest.mark.asyncio
    async def test_promote_idempotent_for_admin(self) -> None:
        user = MagicMock()
        user.role = "admin"
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        )
        session.commit = AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield session

        with patch("app.cli.bootstrap_admin.AsyncSessionLocal", fake_session):
            assert await promote("admin") is True

        session.commit.assert_not_awaited()
