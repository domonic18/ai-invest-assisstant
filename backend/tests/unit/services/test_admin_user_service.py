"""AdminUserService 后台用户管理契约测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.user import AdminUserCreate, AdminUserUpdate
from app.services.admin.users import AdminUserService


def _result_mock(items=None, scalar=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.mark.unit
class TestAdminUserService:
    @pytest.fixture
    def service(self) -> AdminUserService:
        session = AsyncMock()
        session.add = MagicMock()
        return AdminUserService(session)

    @pytest.mark.asyncio
    async def test_list_users(self, service: AdminUserService) -> None:
        mock_user = MagicMock()
        service.session.execute.return_value = _result_mock([mock_user])
        service.session.scalar.return_value = 1

        items, total = await service.list_users()

        assert items == [mock_user]
        assert total == 1

    @pytest.mark.asyncio
    async def test_create_user_success(self, service: AdminUserService) -> None:
        service.session.execute.return_value = _result_mock(scalar=None)
        service.session.get.return_value = None

        data = AdminUserCreate(
            username="tester",
            email="test@example.com",
            password="secret123",
        )
        result = await service.create_user(data)

        assert result.username == "tester"
        service.session.add.assert_called_once()
        service.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, service: AdminUserService) -> None:
        existing = MagicMock()
        service.session.execute.return_value = _result_mock(scalar=existing)

        data = AdminUserCreate(
            username="tester",
            email="test@example.com",
            password="secret123",
        )
        with pytest.raises(ValueError):
            await service.create_user(data)

    @pytest.mark.asyncio
    async def test_update_user(self, service: AdminUserService) -> None:
        user = MagicMock()
        user.username = "old"
        user.email = "old@example.com"
        service.session.get.return_value = user
        service.session.execute.return_value = _result_mock(scalar=None)

        result = await service.update_user(1, AdminUserUpdate(role="admin"))

        assert result == user
        assert user.role == "admin"

    @pytest.mark.asyncio
    async def test_delete_user(self, service: AdminUserService) -> None:
        user = MagicMock()
        service.session.get.return_value = user

        await service.delete_user(1)

        service.session.delete.assert_awaited_once_with(user)

    @pytest.mark.asyncio
    async def test_reset_password(self, service: AdminUserService) -> None:
        user = MagicMock()
        service.session.get.return_value = user

        result = await service.reset_password(1, "newpassword")

        assert result == user
        assert user.password_hash is not None
