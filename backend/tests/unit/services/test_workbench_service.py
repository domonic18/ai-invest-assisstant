"""工作台聚合服务单测：模块降级隔离与数据透传。"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.calendar import CalendarEventResponse
from app.schemas.market import GlobalIndexQuoteResponse
from app.schemas.telegraph import TelegraphResponse
from app.schemas.workbench import WorkbenchResponse, WorkbenchWatchlistGroup
from app.services.workbench import workbench_service

_MODULE = "app.services.workbench.workbench_service"


def _event() -> CalendarEventResponse:
    return CalendarEventResponse(
        id=1,
        event_time=date(2026, 9, 10).isoformat(),
        end_time=None,
        title="FOMC 议息会议",
        category="央行",
        impact_markets=None,
        source=None,
        source_url=None,
        related_symbols=None,
    )


@pytest.mark.unit
class TestGetWorkbench:
    @pytest.mark.asyncio
    async def test_all_modules_populated(self) -> None:
        session = AsyncMock()
        group = WorkbenchWatchlistGroup(id=1, name="核心持仓", ai_review_enabled=True)

        with (
            patch(
                f"{_MODULE}.calendar_service.list_upcoming",
                AsyncMock(return_value=[_event()]),
            ),
            patch(
                f"{_MODULE}.market_review_service.get_market_review",
                AsyncMock(return_value=None),
            ),
            patch(
                f"{_MODULE}.telegraph_service.list_telegraph",
                AsyncMock(return_value=([], 0)),
            ),
            patch(
                f"{_MODULE}.watchlist_quote_service.get_watchlist_groups",
                AsyncMock(return_value=[group]),
            ),
            patch(
                f"{_MODULE}.index_quotation_service.get_index_quotes",
                AsyncMock(return_value=[]),
            ),
            patch(
                f"{_MODULE}.market_stats_service.get_market_stats",
                AsyncMock(return_value=None),
            ),
            patch(
                f"{_MODULE}.global_index_service.get_global_index_quotes",
                AsyncMock(return_value=[]),
            ) as global_mock,
        ):
            result = await workbench_service.get_workbench(session, user_id=3)

        assert isinstance(result, WorkbenchResponse)
        assert result.calendar[0].title == "FOMC 议息会议"
        assert result.review is None
        assert result.watchlist_groups == [group]
        assert result.stats is None
        global_mock.assert_awaited_once_with(session)

    @pytest.mark.asyncio
    async def test_single_module_failure_degrades_others_intact(self) -> None:
        session = AsyncMock()
        group = WorkbenchWatchlistGroup(id=2, name="默认分组", is_default=True)

        with (
            patch(
                f"{_MODULE}.calendar_service.list_upcoming",
                AsyncMock(side_effect=RuntimeError("db boom")),
            ),
            patch(
                f"{_MODULE}.market_review_service.get_market_review",
                AsyncMock(return_value=None),
            ),
            patch(
                f"{_MODULE}.telegraph_service.list_telegraph",
                AsyncMock(return_value=([], 0)),
            ),
            patch(
                f"{_MODULE}.watchlist_quote_service.get_watchlist_groups",
                AsyncMock(return_value=[group]),
            ),
            patch(
                f"{_MODULE}.index_quotation_service.get_index_quotes",
                AsyncMock(side_effect=RuntimeError("redis boom")),
            ),
            patch(
                f"{_MODULE}.market_stats_service.get_market_stats",
                AsyncMock(return_value=None),
            ),
            patch(
                f"{_MODULE}.global_index_service.get_global_index_quotes",
                AsyncMock(
                    return_value=[
                        GlobalIndexQuoteResponse(
                            index_code="GC00Y", index_name="COMEX黄金"
                        )
                    ]
                ),
            ),
        ):
            result = await workbench_service.get_workbench(session, user_id=3)

        assert result.calendar == []
        assert result.indices == []
        assert result.watchlist_groups == [group]
        assert result.global_indices[0].index_code == "GC00Y"

    @pytest.mark.asyncio
    async def test_telegraph_items_only_kept(self) -> None:
        session = AsyncMock()
        item = TelegraphResponse(cls_msg_id=1, publish_time="2026-09-02T10:00:00")

        with (
            patch(
                f"{_MODULE}.calendar_service.list_upcoming",
                AsyncMock(return_value=[]),
            ),
            patch(
                f"{_MODULE}.market_review_service.get_market_review",
                AsyncMock(return_value=None),
            ),
            patch(
                f"{_MODULE}.telegraph_service.list_telegraph",
                AsyncMock(return_value=([item], 57)),
            ) as tg_mock,
            patch(
                f"{_MODULE}.watchlist_quote_service.get_watchlist_groups",
                AsyncMock(return_value=[]),
            ),
            patch(
                f"{_MODULE}.index_quotation_service.get_index_quotes",
                AsyncMock(return_value=[]),
            ),
            patch(
                f"{_MODULE}.market_stats_service.get_market_stats",
                AsyncMock(return_value=None),
            ),
            patch(
                f"{_MODULE}.global_index_service.get_global_index_quotes",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await workbench_service.get_workbench(session, user_id=3)

        assert result.telegraph == [item]
        assert tg_mock.await_args.kwargs["page"] == 1
        assert tg_mock.await_args.kwargs["page_size"] == 12
