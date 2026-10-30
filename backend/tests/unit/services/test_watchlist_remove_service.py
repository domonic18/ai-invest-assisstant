"""WatchlistService.remove_watchlist_stocks 批量删除契约测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.user.watchlist_service import WatchlistService


def _make_session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    return session


def _make_item(stock_code: str, group_id: int) -> MagicMock:
    item = MagicMock()
    item.stock_code = stock_code
    item.group_id = group_id
    return item


def _patch(
    service: WatchlistService,
    *,
    existing: dict[str, MagicMock],
    groups: list[MagicMock],
    group_by_name: MagicMock | None = None,
) -> None:
    service.repo.map_by_user_and_codes = AsyncMock(return_value=existing)
    service.group_repo.list_by_user = AsyncMock(return_value=groups)
    service.group_repo.get_by_name = AsyncMock(return_value=group_by_name)


@pytest.mark.unit
class TestRemoveWatchlistStocks:
    @pytest.mark.asyncio
    async def test_removes_matching_codes_and_reports_missing(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        item_a = _make_item("000001", 10)
        _patch(service, existing={"000001": item_a}, groups=[])

        result = await service.remove_watchlist_stocks(1, ["000001", "600519"])

        assert result == {
            "removed": ["000001"],
            "not_found": ["600519"],
            "mismatch": [],
        }
        session.delete.assert_awaited_once_with(item_a)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_group_name_mismatch_keeps_stock(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        target = MagicMock()
        target.id = 20
        target.name = "日周60"
        other = MagicMock()
        other.id = 10
        other.name = "默认分组"
        item = _make_item("000001", 10)
        _patch(
            service,
            existing={"000001": item},
            groups=[target, other],
            group_by_name=target,
        )

        result = await service.remove_watchlist_stocks(1, ["000001"], "日周60")

        assert result["removed"] == []
        assert result["mismatch"] == [
            {"stock_code": "000001", "actual_group": "默认分组"}
        ]
        session.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_group_name_match_removes(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        target = MagicMock()
        target.id = 20
        item = _make_item("000001", 20)
        _patch(
            service,
            existing={"000001": item},
            groups=[target],
            group_by_name=target,
        )

        result = await service.remove_watchlist_stocks(1, ["000001"], "日周60")

        assert result["removed"] == ["000001"]
        session.delete.assert_awaited_once_with(item)

    @pytest.mark.asyncio
    async def test_unknown_group_name_raises(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        _patch(service, existing={}, groups=[], group_by_name=None)

        with pytest.raises(NotFoundError):
            await service.remove_watchlist_stocks(1, ["000001"], "不存在")

    @pytest.mark.asyncio
    async def test_empty_and_duplicate_codes_no_commit(self) -> None:
        session = _make_session()
        service = WatchlistService(session)
        _patch(service, existing={}, groups=[])

        empty = await service.remove_watchlist_stocks(1, ["", "  "])
        dup = await service.remove_watchlist_stocks(1, ["000001", "000001"])

        assert empty == {"removed": [], "not_found": [], "mismatch": []}
        assert dup["not_found"] == ["000001"]
        session.commit.assert_not_awaited()
