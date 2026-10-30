"""助手自选股分组读写工具单测（mock 服务层，不触网不连库）。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools import watchlist_tools as wt


class _SessionCtx:
    async def __aenter__(self) -> MagicMock:
        return MagicMock()

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _item(code: str) -> SimpleNamespace:
    return SimpleNamespace(
        stock_code=code,
        market="sh",
        created_at=datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc),
    )


def _group(name: str, codes: list[str], *, is_default: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        name=name, is_default=is_default, ai_review_enabled=False, items=[_item(c) for c in codes]
    )


@pytest.mark.unit
class TestGetUserWatchlist:
    @pytest.mark.asyncio
    async def test_returns_groups_with_resolved_names(self) -> None:
        groups = [_group("日周60", ["000001", "600519"])]
        with (
            patch.object(wt, "AsyncSessionLocal", lambda: _SessionCtx()),
            patch(
                "app.services.user.watchlist_service.WatchlistService.list_groups_with_items",
                AsyncMock(return_value=groups),
            ),
            patch(
                "app.repositories.market.stock_repository.StockRepository.get_names_by_codes",
                AsyncMock(return_value={"000001": "平安银行", "600519": "贵州茅台"}),
            ),
        ):
            result = await wt.get_user_watchlist.ainvoke(
                {}, {"configurable": {"user_id": 7}}
            )
        group = result["groups"][0]
        assert group["name"] == "日周60"
        assert group["stocks"][0] == {
            "stock_code": "000001",
            "stock_name": "平安银行",
            "market": "sh",
            "added_at": "2026-10-27",
        }

    @pytest.mark.asyncio
    async def test_group_name_filter_and_unknown_hint(self) -> None:
        groups = [_group("默认分组", ["000001"], is_default=True), _group("日周60", ["600519"])]
        service_mock = AsyncMock(return_value=groups)
        with (
            patch.object(wt, "AsyncSessionLocal", lambda: _SessionCtx()),
            patch(
                "app.services.user.watchlist_service.WatchlistService.list_groups_with_items",
                service_mock,
            ),
            patch(
                "app.repositories.market.stock_repository.StockRepository.get_names_by_codes",
                AsyncMock(return_value={}),
            ),
        ):
            matched = await wt.get_user_watchlist.ainvoke(
                {"group_name": "日周60"}, {"configurable": {"user_id": 7}}
            )
            missed = await wt.get_user_watchlist.ainvoke(
                {"group_name": "不存在"}, {"configurable": {"user_id": 7}}
            )
        assert [g["name"] for g in matched["groups"]] == ["日周60"]
        assert "默认分组" in missed["hint"] and "日周60" in missed["hint"]


@pytest.mark.unit
class TestRemoveWatchlistStocks:
    @pytest.mark.asyncio
    async def test_returns_service_result(self) -> None:
        payload = {"removed": ["000001"], "not_found": ["600519"], "mismatch": []}
        with (
            patch.object(wt, "AsyncSessionLocal", lambda: _SessionCtx()),
            patch(
                "app.services.user.watchlist_service.WatchlistService.remove_watchlist_stocks",
                AsyncMock(return_value=payload),
            ),
        ):
            result = await wt.remove_watchlist_stocks.ainvoke(
                {"stock_codes": ["000001", "600519"], "group_name": "日周60"},
                {"configurable": {"user_id": 7}},
            )
        assert result == payload

    @pytest.mark.asyncio
    async def test_unknown_group_returns_error_hint(self) -> None:
        from app.core.exceptions import NotFoundError

        with (
            patch.object(wt, "AsyncSessionLocal", lambda: _SessionCtx()),
            patch(
                "app.services.user.watchlist_service.WatchlistService.remove_watchlist_stocks",
                AsyncMock(side_effect=NotFoundError("Group not found")),
            ),
        ):
            result = await wt.remove_watchlist_stocks.ainvoke(
                {"stock_codes": ["000001"], "group_name": "不存在"},
                {"configurable": {"user_id": 7}},
            )
        assert "不存在" in result["error"]
        assert "get_user_watchlist" in result["error"]
