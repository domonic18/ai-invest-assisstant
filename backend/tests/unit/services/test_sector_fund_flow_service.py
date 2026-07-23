"""Unit tests for sector fund flow trend service."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.capital_fund_flow_sector import SectorFundFlow
from app.services import sector_fund_flow_service


def _row(day: date, code: str, name: str, amount: str | None) -> SectorFundFlow:
    return SectorFundFlow(
        sector_code=code,
        sector_name=name,
        sector_type="industry",
        trade_date=day,
        main_net_inflow=Decimal(amount) if amount is not None else None,
    )


@pytest.mark.unit
class TestGetSectorFlowTrend:
    @pytest.mark.asyncio
    async def test_trend_aligns_values_and_orders_by_abs_total(self) -> None:
        rows = [
            # 乱序输入；半导体两日 +216/+100，银行 -32/-18，电力仅 07-21 有值
            _row(date(2026, 7, 21), "BK1036", "半导体", "21604000000"),
            _row(date(2026, 7, 20), "BK1036", "半导体", "10000000000"),
            _row(date(2026, 7, 21), "BK0475", "银行", "-3210000000"),
            _row(date(2026, 7, 20), "BK0475", "银行", "-1800000000"),
            _row(date(2026, 7, 21), "BK0428", "电力", "-1840000000"),
        ]
        with patch.object(
            sector_fund_flow_service.sector_fund_flow_repository,
            "list_recent",
            new=AsyncMock(return_value=rows),
        ) as mock_list:
            result = await sector_fund_flow_service.get_sector_flow_trend(
                AsyncMock(), "industry", 60
            )

        mock_list.assert_awaited_once()
        assert mock_list.await_args.args[1:] == ("industry", 60)
        assert result.dates == [date(2026, 7, 20), date(2026, 7, 21)]
        # 累计 |净流入|：半导体 316.04 > 银行 50.1 > 电力 18.4
        assert [s.code for s in result.sectors] == ["BK1036", "BK0475", "BK0428"]
        assert result.sectors[0].name == "半导体"
        assert result.sectors[0].values == [100.0, 216.04]
        assert result.sectors[1].values == [-18.0, -32.1]
        # 缺口为 None
        assert result.sectors[2].values == [None, -18.4]

    @pytest.mark.asyncio
    async def test_trend_skips_null_amounts_in_totals(self) -> None:
        rows = [
            _row(date(2026, 7, 21), "BK1036", "半导体", None),
            _row(date(2026, 7, 21), "BK0475", "银行", "-3210000000"),
        ]
        with patch.object(
            sector_fund_flow_service.sector_fund_flow_repository,
            "list_recent",
            new=AsyncMock(return_value=rows),
        ):
            result = await sector_fund_flow_service.get_sector_flow_trend(
                AsyncMock(), "industry", 60
            )

        # main_net_inflow 为 None 的板块不进入 sectors（无累计值）
        assert [s.code for s in result.sectors] == ["BK0475"]
        assert result.dates == [date(2026, 7, 21)]

    @pytest.mark.asyncio
    async def test_trend_empty(self) -> None:
        with patch.object(
            sector_fund_flow_service.sector_fund_flow_repository,
            "list_recent",
            new=AsyncMock(return_value=[]),
        ):
            result = await sector_fund_flow_service.get_sector_flow_trend(
                AsyncMock(), "industry", 60
            )

        assert result.dates == []
        assert result.sectors == []
