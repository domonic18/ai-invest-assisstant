"""Unit tests for hotspot API endpoints."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestHotspotEndpoints:
    def _sector_mock(self) -> MagicMock:
        sector = MagicMock()
        sector.sector_code = "BK01"
        sector.sector_name = "银行"
        sector.sector_type = "industry"
        sector.trade_date = date(2024, 1, 1)
        sector.change_pct = Decimal("1.5")
        sector.main_net_inflow = Decimal("1000000")
        sector.super_large_net = Decimal("500000")
        sector.large_net = Decimal("300000")
        sector.medium_net = Decimal("200000")
        sector.small_net = Decimal("0")
        sector.top_stock_code = "000001"
        sector.top_stock_name = "平安银行"
        sector.created_at = datetime(2024, 1, 1, 0, 0, 0)
        return sector

    @patch("app.api.v1.hotspot.hotspot_service.list_sectors")
    def test_list_hotspots(self, mock_list, client) -> None:
        mock_list.return_value = ([self._sector_mock()], 1)
        response = client.get("/api/v1/hotspot/?sector_type=industry")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["sector_name"] == "银行"

    @patch("app.api.v1.hotspot.hotspot_service.list_sectors")
    def test_list_hotspots_with_trade_date(self, mock_list, client) -> None:
        mock_list.return_value = ([], 0)
        response = client.get("/api/v1/hotspot/?trade_date=2024-01-01")
        assert response.status_code == 200
        assert response.json()["items"] == []
