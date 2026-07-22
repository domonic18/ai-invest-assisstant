"""Unit tests for index call-auction trend service."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.index_auction import IndexAuction
from app.services import auction_service


def _row(day: date, code: str, amount: str) -> IndexAuction:
    return IndexAuction(
        trade_date=day,
        index_code=code,
        auction_amount=Decimal(amount),
        source="sina",
    )


@pytest.mark.unit
class TestGetIndexAuctionTrend:
    @pytest.mark.asyncio
    async def test_trend_aligns_series_and_converts_to_yi(self) -> None:
        rows = [
            # 07-20 缺科创50，07-21 三指数齐全（乱序输入验证日期升序）
            _row(date(2026, 7, 21), "sh000001", "9581000000"),
            _row(date(2026, 7, 20), "sh000001", "9000000000"),
            _row(date(2026, 7, 20), "sz399006", "3620000000"),
            _row(date(2026, 7, 21), "sh000688", "1201000000"),
            _row(date(2026, 7, 21), "sz399006", "3620000000"),
        ]
        with patch.object(
            auction_service.index_auction_repository,
            "list_recent",
            new=AsyncMock(return_value=rows),
        ):
            result = await auction_service.get_index_auction_trend(AsyncMock(), days=30)

        assert result.dates == [date(2026, 7, 20), date(2026, 7, 21)]
        # series 顺序固定：上证指数 / 科创50 / 创业板指
        assert [s.code for s in result.series] == ["sh000001", "sh000688", "sz399006"]
        assert [s.name for s in result.series] == ["上证指数", "科创50", "创业板指"]
        assert result.series[0].values == [90.0, 95.81]
        # 缺口为 None
        assert result.series[1].values == [None, 12.01]
        assert result.series[2].values == [36.2, 36.2]

    @pytest.mark.asyncio
    async def test_trend_empty(self) -> None:
        with patch.object(
            auction_service.index_auction_repository,
            "list_recent",
            new=AsyncMock(return_value=[]),
        ):
            result = await auction_service.get_index_auction_trend(AsyncMock(), days=30)

        assert result.dates == []
        assert all(s.values == [] for s in result.series)

    @pytest.mark.asyncio
    async def test_trend_with_date_range_uses_list_range(self) -> None:
        rows = [
            _row(date(2026, 7, 1), "sh000001", "9000000000"),
            _row(date(2026, 7, 2), "sh000001", "9500000000"),
        ]
        list_range = AsyncMock(return_value=rows)
        list_recent = AsyncMock()
        with (
            patch.object(
                auction_service.index_auction_repository,
                "list_range",
                new=list_range,
            ),
            patch.object(
                auction_service.index_auction_repository,
                "list_recent",
                new=list_recent,
            ),
        ):
            result = await auction_service.get_index_auction_trend(
                AsyncMock(),
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 2),
            )

        list_range.assert_awaited_once()
        assert list_range.await_args.args[1:] == (date(2026, 7, 1), date(2026, 7, 2))
        list_recent.assert_not_awaited()
        assert result.dates == [date(2026, 7, 1), date(2026, 7, 2)]
        assert result.series[0].values == [90.0, 95.0]

    @pytest.mark.asyncio
    async def test_trend_with_only_end_date_defaults_start(self) -> None:
        list_range = AsyncMock(return_value=[])
        with patch.object(
            auction_service.index_auction_repository,
            "list_range",
            new=list_range,
        ):
            await auction_service.get_index_auction_trend(
                AsyncMock(), end_date=date(2026, 7, 2)
            )

        assert list_range.await_args.args[1] == date.min
        assert list_range.await_args.args[2] == date(2026, 7, 2)
