"""交易日历服务单测（归位查询：≤ 某日的最近交易日）。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import trade_calendar_service


@pytest.mark.unit
class TestResolveTradeDateOnOrBefore:
    @pytest.mark.asyncio
    async def test_returns_kline_max_when_covered(self) -> None:
        with patch(
            "app.services.market.trade_calendar_service.fetch_max_daily_date_on_or_before",
            AsyncMock(return_value=date(2026, 9, 4)),
        ):
            result = await trade_calendar_service.resolve_trade_date_on_or_before(
                MagicMock(), date(2026, 9, 5)
            )
        assert result == date(2026, 9, 4)

    @pytest.mark.asyncio
    async def test_weekend_walks_back_to_friday_without_kline(self) -> None:
        with patch(
            "app.services.market.trade_calendar_service.fetch_max_daily_date_on_or_before",
            AsyncMock(return_value=None),
        ):
            result = await trade_calendar_service.resolve_trade_date_on_or_before(
                MagicMock(), date(2026, 9, 5)
            )
        assert result == date(2026, 9, 4)
