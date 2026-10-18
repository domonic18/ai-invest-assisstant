"""AdminUserGroupService 与 AdminUserService 组分配契约测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.user import AdminUserUpdate
from app.schemas.user_group import UserGroupCreate, UserGroupUpdate
from app.services.admin.user_groups import AdminUserGroupService


def _result_mock(items=None, scalar=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.mark.unit
class TestAdminUserGroupService:
    @pytest.fixture
    def service(self) -> AdminUserGroupService:
        session = AsyncMock()
        session.add = MagicMock()
        return AdminUserGroupService(session)

    @pytest.mark.asyncio
    async def test_create_group_success(self, service) -> None:
        service.session.execute.return_value = _result_mock(scalar=None)
        group = await service.create_group(
            UserGroupCreate(name="访客组", permissions=["kb", "news"])
        )
        assert group.permissions == ["kb", "news"]
        service.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_group_duplicate_name_raises_409(self, service) -> None:
        service.session.execute.return_value = _result_mock(scalar=MagicMock())
        with pytest.raises(ConflictError):
            await service.create_group(UserGroupCreate(name="已有组"))

    @pytest.mark.asyncio
    async def test_update_group_renames_and_sets_permissions(self, service) -> None:
        group = MagicMock()
        group.name = "旧名"
        service.session.get.return_value = group
        service.session.execute.return_value = _result_mock(scalar=None)
        result = await service.update_group(
            1, UserGroupUpdate(name="新名", permissions=["kb"])
        )
        assert result is group
        assert group.name == "新名"
        assert group.permissions == ["kb"]

    @pytest.mark.asyncio
    async def test_update_group_not_found(self, service) -> None:
        service.session.get.return_value = None
        with pytest.raises(NotFoundError):
            await service.update_group(99, UserGroupUpdate(name="任意"))

    @pytest.mark.asyncio
    async def test_delete_group_with_members_raises_409(self, service) -> None:
        group = MagicMock()
        service.session.get.return_value = group
        service.session.scalar.return_value = 3
        with pytest.raises(ConflictError) as exc:
            await service.delete_group(1)
        assert "3 个成员" in str(exc.value)
        service.session.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_group_empty_deletes(self, service) -> None:
        group = MagicMock()
        service.session.get.return_value = group
        service.session.scalar.return_value = 0
        await service.delete_group(1)
        service.session.delete.assert_awaited_once_with(group)


@pytest.mark.unit
class TestAdminUserServiceGroupAssignment:
    @pytest.fixture
    def service(self):
        from app.services.admin.users import AdminUserService

        session = AsyncMock()
        session.add = MagicMock()
        return AdminUserService(session)

    @pytest.mark.asyncio
    async def test_update_user_group_id_zero_clears_group(self, service) -> None:
        user = MagicMock()
        service.session.get.side_effect = [user]
        result = await service.update_user(1, AdminUserUpdate(group_id=0))
        assert result is user
        assert user.group_id is None

    @pytest.mark.asyncio
    async def test_update_user_assigns_existing_group(self, service) -> None:
        user = MagicMock()
        group = MagicMock()
        service.session.get.side_effect = [user, group]
        await service.update_user(1, AdminUserUpdate(group_id=5))
        assert user.group_id == 5

    @pytest.mark.asyncio
    async def test_update_user_unknown_group_raises_404(self, service) -> None:
        user = MagicMock()
        service.session.get.side_effect = [user, None]
        with pytest.raises(NotFoundError):
            await service.update_user(1, AdminUserUpdate(group_id=99))

    @pytest.mark.asyncio
    async def test_update_user_omitted_group_keeps_unchanged(self, service) -> None:
        user = MagicMock()
        user.username = "same"
        user.email = "same@example.com"
        service.session.get.return_value = user
        service.session.execute.return_value = _result_mock(scalar=None)
        await service.update_user(1, AdminUserUpdate())
        # 仅查一次 user，无组查找，group_id 不被触碰
        assert service.session.get.await_count == 1
