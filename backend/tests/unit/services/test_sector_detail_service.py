"""sector_detail_service 板块详情聚合契约测试。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.sector_detail import SectorDetailResponse
from app.services.market import sector_detail_service


def _kline_row(trade_date, open_, high, low, close, volume=1000, amount=2.0e8):
    return SimpleNamespace(
        trade_date=trade_date,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
    )


def _quote_row(sector_name, trade_date=None):
    return SimpleNamespace(
        sector_name=sector_name,
        trade_date=trade_date or date(2026, 9, 10),
        close=101.0,
        change_pct=1.2,
        amount=3.0e10,
        turnover_rate=2.5,
        up_count=90,
        down_count=10,
        leader_stock_name="某龙头",
    )


def _session_mock() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    session.scalar.return_value = None
    return session


@pytest.mark.unit
class TestGetSectorDetail:
    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_sector(self) -> None:
        session = _session_mock()
        result = await sector_detail_service.get_sector_detail(
            session, "industry", "BK0000"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_without_ths_kline(self) -> None:
        """无同名 THS 板块 → 404（链式合成兜底已移除）。"""
        session = _session_mock()
        sector_detail_service.sector_quote_repository.latest_sector_quote = AsyncMock(
            return_value=_quote_row("AIGC概念")
        )
        sector_detail_service.kline_repository.list_sector_kline_by_name = AsyncMock(
            return_value=[]
        )

        result = await sector_detail_service.get_sector_detail(
            session, "concept", "BK0001"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_identity_falls_back_to_fund_flow(self) -> None:
        """板块不在最新快照池（快照无该代码）时，从资金流行取板块名。"""
        session = _session_mock()
        sector_detail_service.sector_quote_repository.latest_sector_quote = AsyncMock(
            return_value=None
        )
        sector_detail_service.sector_fund_flow_repository.get_latest_by_code = AsyncMock(
            return_value=SimpleNamespace(sector_name="半导体")
        )
        sector_detail_service.kline_repository.list_sector_kline_by_name = AsyncMock(
            return_value=[_kline_row(date(2026, 9, 10), 100.0, 105.0, 99.0, 104.0)]
        )
        sector_detail_service.sector_fund_flow_repository.list_history_by_code = (
            AsyncMock(return_value=[])
        )
        sector_detail_service.anomaly_repository.list_sector_anomalies_by_code = (
            AsyncMock(return_value=[])
        )

        detail = await sector_detail_service.get_sector_detail(
            session, "industry", "BK1036"
        )

        assert detail is not None
        assert detail.sector_name == "半导体"
        assert detail.snapshot is None

    @pytest.mark.asyncio
    async def test_ths_bars_with_change_pct_and_anomaly_days(self) -> None:
        session = _session_mock()
        sector_detail_service.sector_quote_repository.latest_sector_quote = AsyncMock(
            return_value=_quote_row("半导体")
        )
        sector_detail_service.sector_fund_flow_repository.list_history_by_code = (
            AsyncMock(
                return_value=[
                    SimpleNamespace(
                        trade_date=date(2026, 9, 10),
                        main_net_inflow=-6.5e9,
                        super_large_net=-4.0e9,
                        large_net=-2.5e9,
                        medium_net=1.0e8,
                        small_net=2.0e8,
                    )
                ]
            )
        )
        sector_detail_service.kline_repository.list_sector_kline_by_name = AsyncMock(
            return_value=[
                _kline_row(date(2026, 9, 9), 100.0, 105.0, 99.0, 104.0),
                _kline_row(date(2026, 9, 10), 104.0, 106.0, 102.0, 101.0),
            ]
        )
        sector_detail_service.anomaly_repository.list_sector_anomalies_by_code = (
            AsyncMock(
                return_value=[
                    SimpleNamespace(
                        trade_date=date(2026, 9, 10),
                        anomaly_types=["price", "volume"],
                        strength=80,
                        attribution_category="resonance",
                        attribution_summary="量价齐升",
                    )
                ]
            )
        )

        detail = await sector_detail_service.get_sector_detail(
            session, "industry", "BK1036"
        )

        assert isinstance(detail, SectorDetailResponse)
        assert detail.sector_name == "半导体"
        assert detail.bars[0].change_pct is None
        assert detail.bars[1].close == 101.0
        assert detail.bars[1].change_pct == round((101.0 / 104.0 - 1) * 100, 4)
        assert detail.fund_flow[0].main_net_inflow == -6.5e9
        assert detail.fund_flow[0].super_large_net == -4.0e9
        assert detail.fund_flow[0].small_net == 2.0e8
        assert detail.anomaly_days[0].anomaly_types == ["price", "volume"]
        assert detail.snapshot is not None and detail.snapshot.up_count == 90
