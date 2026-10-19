"""港股复盘卡片服务单测：恒生系收盘卡映射 + 涨幅榜行映射与休市空态。"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import hk_review_service


def _all_mock(rows: list) -> MagicMock:
    return MagicMock(all=MagicMock(return_value=rows))


@pytest.mark.unit
class TestGetHkReviewIndices:
    @pytest.mark.asyncio
    async def test_maps_hsi_family_with_names_and_trend(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _all_mock(
                [
                    ("HSI", Decimal("25390.52"), Decimal("1.24"), date(2026, 10, 16)),
                    ("HSCEI", Decimal("9100.00"), Decimal("0.88"), date(2026, 10, 16)),
                ]
            ),
            _all_mock([("HSI", Decimal("25100.0")), ("HSI", Decimal("25390.52"))]),
        ]

        cards = await hk_review_service.get_hk_review_indices(session)

        assert [c.index_code for c in cards] == ["HSI", "HSTECH", "HSCEI"]
        assert cards[0].index_name == "恒生指数"
        assert cards[0].close == 25390.52
        assert cards[0].trade_date == date(2026, 10, 16)
        assert cards[0].trend == [25100.0, 25390.52]
        assert cards[1].close is None
        assert cards[1].trend == []

    @pytest.mark.asyncio
    async def test_trade_date_passed_to_closes_queries(self) -> None:
        """复盘历史日：截断参数透传仓储（最新收盘与趋势均不晚于该日）。"""
        session = AsyncMock()
        session.execute.side_effect = [
            _all_mock([("HSI", Decimal("25000.0"), Decimal("-0.5"), date(2026, 10, 9))]),
            _all_mock([]),
        ]

        with (
            patch.object(
                hk_review_service.global_index_repository,
                "map_latest_closes",
                wraps=hk_review_service.global_index_repository.map_latest_closes,
            ) as spy_latest,
            patch.object(
                hk_review_service.global_index_repository,
                "map_recent_closes",
                wraps=hk_review_service.global_index_repository.map_recent_closes,
            ) as spy_recent,
        ):
            cards = await hk_review_service.get_hk_review_indices(
                session, trade_date=date(2026, 10, 12)
            )

        assert len(cards) == 3
        assert cards[0].trade_date == date(2026, 10, 9)
        assert cards[1].close is None
        assert spy_latest.await_args.kwargs["on_or_before"] == date(2026, 10, 12)
        assert spy_recent.await_args.kwargs["on_or_before"] == date(2026, 10, 12)


@pytest.mark.unit
class TestGetHkGainers:
    @pytest.mark.asyncio
    async def test_maps_rows_to_items(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _all_mock(
            [
                SimpleNamespace(
                    stock_code="00700",
                    stock_name="腾讯控股",
                    close=Decimal("417.80"),
                    change_pct=Decimal("5.12"),
                    amount=Decimal("8651707711.00"),
                )
            ]
        )

        items = await hk_review_service.get_hk_gainers(session, trade_date=date(2026, 10, 16))

        assert len(items) == 1
        assert items[0].stock_code == "00700"
        assert items[0].stock_name == "腾讯控股"
        assert items[0].close == 417.8
        assert items[0].change_pct == 5.12
        assert items[0].amount == 8651707711.0
        assert items[0].trade_date == date(2026, 10, 16)

    @pytest.mark.asyncio
    async def test_empty_on_hk_holiday(self) -> None:
        """显式复盘日为港股休市日（2026-10-19 重阳节翌日）→ 空列表。"""
        session = AsyncMock()
        session.execute.return_value = _all_mock([])

        items = await hk_review_service.get_hk_gainers(session, trade_date=date(2026, 10, 19))

        assert items == []

    @pytest.mark.asyncio
    async def test_live_view_resolves_latest_hk_session(self) -> None:
        """实时视图（未传日期）：归位最近港股交易日再查（避免休市日空榜）。"""
        session = AsyncMock()
        session.execute.return_value = _all_mock([])

        with (
            patch.object(hk_review_service, "today_cn", return_value=date(2026, 10, 19)),
            patch.object(
                hk_review_service,
                "_latest_hk_session",
                AsyncMock(return_value=date(2026, 10, 16)),
            ) as spy_session,
        ):
            await hk_review_service.get_hk_gainers(session)

        spy_session.assert_awaited_once_with(session, date(2026, 10, 19))
        compiled = session.execute.await_args.args[0].compile()
        assert date(2026, 10, 16) in compiled.params.values()


@pytest.mark.unit
class TestLatestHkSession:
    def _session(self, calendar_rows: list) -> AsyncMock:
        session = AsyncMock()
        scalars = MagicMock(all=MagicMock(return_value=calendar_rows))
        session.execute.return_value = MagicMock(scalars=MagicMock(return_value=scalars))
        return session

    @pytest.mark.asyncio
    async def test_returns_latest_trading_day(self) -> None:
        """重阳节翌日（2026-10-19 休市）归位 10-16（周五）。"""
        rows = [
            SimpleNamespace(calendar_date=date(2026, 10, d), is_trading=bool(flag))
            for d, flag in [(12, 0), (13, 0), (14, 0), (15, 0), (16, 1), (17, 0), (19, 0)]
        ]
        session = self._session(rows)

        day = await hk_review_service._latest_hk_session(session, date(2026, 10, 19))

        assert day == date(2026, 10, 16)

    @pytest.mark.asyncio
    async def test_no_calendar_coverage_returns_day_as_is(self) -> None:
        session = self._session([])

        day = await hk_review_service._latest_hk_session(session, date(2026, 10, 19))

        assert day == date(2026, 10, 19)
