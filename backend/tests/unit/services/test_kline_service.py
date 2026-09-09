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
