"""WatchlistService 分组业务契约测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.user import (
    WatchlistGroupCreate,
    WatchlistGroupUpdate,
    WatchlistItemCreate,
)
from app.services.user.watchlist_service import GroupLimitError, WatchlistService


def _make_session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


def _make_group(
    group_id: int,
    user_id: int = 1,
    *,
    name: str = "科技",
    sort_order: int = 1,
    is_default: bool = False,
    items: list | None = None,
) -> MagicMock:
    group = MagicMock()
    group.id = group_id
    group.user_id = user_id
    group.name = name
    group.sort_order = sort_order
    group.is_default = is_default
    group.ai_review_enabled = False
    group.items = items if items is not None else []
    return group


def _patch_repo(service: WatchlistService, **methods: AsyncMock) -> None:
    for name, mock in methods.items():
        setattr(service.group_repo, name, mock)


@pytest.mark.unit
class TestDefaultGroup:
    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing_default(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        existing = _make_group(7, name="默认分组", is_default=True)
        _patch_repo(service, get_default=AsyncMock(return_value=existing))

        group = await service.get_or_create_default_group(1)

        assert group is existing
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_or_create_creates_when_missing(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        _patch_repo(service, get_default=AsyncMock(return_value=None))
        session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 7))

        group = await service.get_or_create_default_group(1)

        assert group.is_default is True
        assert group.name == "默认分组"
        assert group.id == 7
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestGroupCrud:
    @pytest.mark.asyncio
    async def test_create_group_rejects_duplicate_name(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        _patch_repo(
            service,
            count_by_user=AsyncMock(return_value=1),
            get_by_name=AsyncMock(return_value=_make_group(7)),
        )

        with pytest.raises(ValueError, match="already exists"):
            await service.create_group(1, WatchlistGroupCreate(name="科技"))

        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_group_rejects_over_limit(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        _patch_repo(
            service,
            count_by_user=AsyncMock(return_value=20),
            get_by_name=AsyncMock(return_value=None),
        )

        with pytest.raises(GroupLimitError):
            await service.create_group(1, WatchlistGroupCreate(name="新组"))

    @pytest.mark.asyncio
    async def test_update_group_renames_and_toggles(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        group = _make_group(7)
        _patch_repo(
            service,
            get_by_user_and_id=AsyncMock(return_value=group),
            get_by_name=AsyncMock(return_value=None),
        )

        result = await service.update_group(
            1, 7, WatchlistGroupUpdate(name="新能源", ai_review_enabled=True)
        )

        assert result.name == "新能源"
        assert result.ai_review_enabled is True
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_group_rejects_default_rename(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        default_group = _make_group(7, name="默认分组", is_default=True)
        _patch_repo(service, get_by_user_and_id=AsyncMock(return_value=default_group))

        with pytest.raises(ValueError, match="Default group"):
            await service.update_group(1, 7, WatchlistGroupUpdate(name="改名"))

    @pytest.mark.asyncio
    async def test_delete_group_moves_items_to_default(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        item_a, item_b = MagicMock(), MagicMock()
        target = _make_group(8, items=[item_a, item_b])
        default_group = _make_group(7, name="默认分组", is_default=True)
        _patch_repo(
            service,
            get_by_user_and_id=AsyncMock(return_value=target),
            get_default=AsyncMock(return_value=default_group),
        )
        session.delete = AsyncMock()

        await service.delete_group(1, 8)

        assert item_a.group_id == 7
        assert item_b.group_id == 7
        session.delete.assert_awaited_once_with(target)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_group_rejects_default(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        default_group = _make_group(7, name="默认分组", is_default=True)
        _patch_repo(service, get_by_user_and_id=AsyncMock(return_value=default_group))

        with pytest.raises(ValueError, match="Default group"):
            await service.delete_group(1, 7)

    @pytest.mark.asyncio
    async def test_reorder_rejects_mismatched_ids(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        _patch_repo(
            service,
            list_by_user=AsyncMock(return_value=[_make_group(7), _make_group(8)]),
        )

        with pytest.raises(ValueError, match="does not match"):
            await service.reorder_groups(1, [7])

    @pytest.mark.asyncio
    async def test_reorder_assigns_sort_order(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        group_a, group_b = _make_group(7), _make_group(8)
        _patch_repo(
            service,
            list_by_user=AsyncMock(return_value=[group_a, group_b]),
        )

        await service.reorder_groups(1, [8, 7])

        assert group_b.sort_order == 0
        assert group_a.sort_order == 1
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestItems:
    @pytest.mark.asyncio
    async def test_add_item_defaults_to_default_group(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        default_group = _make_group(7, name="默认分组", is_default=True)
        _patch_repo(service, get_default=AsyncMock(return_value=default_group))
        service.repo.get_by_user_and_stock = AsyncMock(return_value=None)
        session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 99))
        user = MagicMock()
        user.id = 1

        item = await service.add_watchlist_item(
            user, WatchlistItemCreate(stock_code="600519")
        )

        assert item.group_id == 7

    @pytest.mark.asyncio
    async def test_add_item_rejects_foreign_group(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        service.repo.get_by_user_and_stock = AsyncMock(return_value=None)
        _patch_repo(service, get_by_user_and_id=AsyncMock(return_value=None))
        user = MagicMock()
        user.id = 1

        with pytest.raises(ValueError, match="Group not found"):
            await service.add_watchlist_item(
                user, WatchlistItemCreate(stock_code="600519", group_id=999)
            )

    @pytest.mark.asyncio
    async def test_move_item_rejects_foreign_target(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        item = MagicMock()
        item.user_id = 1
        item.group_id = 7
        session.get = AsyncMock(return_value=item)
        _patch_repo(service, get_by_user_and_id=AsyncMock(return_value=None))

        with pytest.raises(ValueError, match="Target group not found"):
            await service.move_watchlist_item(1, 99, 999)

    @pytest.mark.asyncio
    async def test_remove_item_deletes_owned(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        item = MagicMock()
        item.user_id = 1
        session.get = AsyncMock(return_value=item)
        session.delete = AsyncMock()

        await service.remove_watchlist_item(1, 99)

        session.delete.assert_awaited_once_with(item)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_item_rejects_missing(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        session.get = AsyncMock(return_value=None)

        with pytest.raises(LookupError):
            await service.remove_watchlist_item(1, 99)
