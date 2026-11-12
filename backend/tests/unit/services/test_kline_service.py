"""个股 K 线服务单测（日线换手率/振幅/涨跌幅透出）。"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.kline import KlineDaily
from app.services.market import kline_service


def _bar(day: date, close: str, **extra: Decimal | None) -> KlineDaily:
    return KlineDaily(
        stock_code="600519",
        trade_date=day,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("98"),
        close=Decimal(close),
        volume=1000,
        amount=Decimal("110000"),
        **extra,
    )


@pytest.mark.unit
class TestGetStockKlineFields:
    @pytest.mark.asyncio
    async def test_daily_passes_through_derived_fields(self) -> None:
        rows = [
            _bar(
                date(2026, 9, 3),
                "300",
                change_pct=Decimal("1.50"),
                amplitude=Decimal("4.20"),
                turnover_rate=Decimal("2.31"),
            ),
            _bar(date(2026, 9, 4), "318", change_pct=None, amplitude=None, turnover_rate=None),
        ]
        with (
            patch.object(
                kline_service, "get_stock_by_code", AsyncMock(return_value=MagicMock())
            ),
            patch.object(
                kline_service, "fetch_daily_bars", AsyncMock(return_value=list(reversed(rows)))
            ),
            patch.object(
                kline_service, "count_daily_bars", AsyncMock(return_value=len(rows))
            ),
            patch.object(
                kline_service.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 4)),
            ),
        ):
            data = await kline_service.get_stock_kline(AsyncMock(), "600519", "daily", 250)

        assert [b["date"] for b in data["bars"]] == [date(2026, 9, 3), date(2026, 9, 4)]
        first, second = data["bars"]
        assert first["change_pct"] == 1.5
        assert first["amplitude"] == 4.2
        assert first["turnover_rate"] == 2.31
        # 缺失列透传 None，由前端按前收/高低点派生
        assert second["change_pct"] is None
        assert second["amplitude"] is None
        assert second["turnover_rate"] is None
        # 最近交易日透出（交易日历权威），前端据此判定数据落后并自动补采
        assert data["latest_trade_date"] == date(2026, 9, 4)
        # 历史根数充足时无需补采
        assert data["needs_backfill"] is False
        assert data["min_healthy_bars"] == kline_service.MIN_HEALTHY_BARS


@pytest.mark.unit
class TestIsHistoryTruncated:
    """历史截断判据：上市已久但库内日 K 根数不足 → 需要补采全历史。"""

    def test_listed_long_ago_with_few_bars_is_truncated(self) -> None:
        assert (
            kline_service.is_history_truncated(
                market="sh",
                listing_date=date(2020, 1, 1),
                latest_trade_date=date(2026, 11, 11),
                bar_count=6,
            )
            is True
        )

    def test_enough_bars_is_not_truncated(self) -> None:
        assert (
            kline_service.is_history_truncated(
                market="sh",
                listing_date=date(2020, 1, 1),
                latest_trade_date=date(2026, 11, 11),
                bar_count=kline_service.MIN_HEALTHY_BARS,
            )
            is False
        )

    def test_recent_listing_is_not_truncated(self) -> None:
        """次新股 bar 少属正常，不触发补采。"""
        assert (
            kline_service.is_history_truncated(
                market="sz",
                listing_date=date(2026, 10, 1),
                latest_trade_date=date(2026, 11, 11),
                bar_count=6,
            )
            is False
        )

    def test_non_a_share_market_is_not_truncated(self) -> None:
        """港股日 K 只保留近几日，按设计不适用完整历史判据。"""
        assert (
            kline_service.is_history_truncated(
                market="hk",
                listing_date=date(2020, 1, 1),
                latest_trade_date=date(2026, 11, 11),
                bar_count=6,
            )
            is False
        )

    def test_missing_listing_date_is_not_truncated(self) -> None:
        assert (
            kline_service.is_history_truncated(
                market="sh",
                listing_date=None,
                latest_trade_date=date(2026, 11, 11),
                bar_count=6,
            )
            is False
        )

    def test_empty_history_is_not_truncated(self) -> None:
        """库内无数据走「缺数据」补采分支，不重复报历史截断。"""
        assert (
            kline_service.is_history_truncated(
                market="sh",
                listing_date=date(2020, 1, 1),
                latest_trade_date=date(2026, 11, 11),
                bar_count=0,
            )
            is False
        )


@pytest.mark.unit
class TestGetStockKlineBackfillFlag:
    @pytest.mark.asyncio
    async def test_truncated_history_reports_needs_backfill(self) -> None:
        stock = MagicMock()
        stock.market = "sh"
        stock.listing_date = date(2020, 1, 1)
        stock.stock_name = "贵州茅台"

        with (
            patch.object(
                kline_service, "get_stock_by_code", AsyncMock(return_value=stock)
            ),
            patch.object(
                kline_service, "fetch_daily_bars", AsyncMock(return_value=list(reversed([_bar(date(2026, 11, 10), "1")])))
            ),
            patch.object(kline_service, "count_daily_bars", AsyncMock(return_value=6)),
            patch.object(
                kline_service.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 11, 11)),
            ),
        ):
            data = await kline_service.get_stock_kline(AsyncMock(), "600519", "daily", 250)

        assert data["needs_backfill"] is True
        assert data["min_healthy_bars"] == kline_service.MIN_HEALTHY_BARS

    @pytest.mark.asyncio
    async def test_non_daily_period_never_reports_backfill(self) -> None:
        """周/月聚合视图不做历史深度判定。"""
        stock = MagicMock()
        stock.market = "sh"
        stock.listing_date = date(2020, 1, 1)
        stock.stock_name = "贵州茅台"

        with (
            patch.object(
                kline_service, "get_stock_by_code", AsyncMock(return_value=stock)
            ),
            patch.object(
                kline_service, "fetch_aggregated_bars", AsyncMock(return_value=[])
            ),
            patch.object(kline_service, "count_daily_bars", AsyncMock(return_value=6)),
            patch.object(
                kline_service.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 11, 11)),
            ),
        ):
            data = await kline_service.get_stock_kline(AsyncMock(), "600519", "weekly", 250)

        assert data["needs_backfill"] is False
