"""热点板块 API 端点契约测试。"""

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
    def test_amount_fields_serialize_as_numbers(self, mock_list, client) -> None:
        """金额字段必须是 JSON number：Decimal 会序列化成字符串，前端 toFixed 直接崩。"""
        mock_list.return_value = ([self._sector_mock()], 1)
        response = client.get("/api/v1/hotspot/")
        item = response.json()["items"][0]
        for field in ("change_pct", "main_net_inflow", "super_large_net"):
            assert isinstance(item[field], (int, float)), f"{field} 应为 number"

    @patch("app.api.v1.hotspot.hotspot_service.list_sectors")
    def test_list_hotspots_with_trade_date(self, mock_list, client) -> None:
        mock_list.return_value = ([], 0)
        response = client.get("/api/v1/hotspot/?trade_date=2024-01-01")
        assert response.status_code == 200
        assert response.json()["items"] == []

    @patch("app.api.v1.hotspot.hotspot_service.list_sectors")
    def test_page_size_200_allowed_for_signal_card(self, mock_list, client) -> None:
        """热点页信号卡单页拉全量板块（~500 行有界清单），200 须放行。"""
        mock_list.return_value = ([], 0)
        response = client.get("/api/v1/hotspot/?page=1&page_size=200")
        assert response.status_code == 200
        kwargs = mock_list.call_args.kwargs
        assert kwargs["page_size"] == 200

    def test_page_size_over_limit_returns_422(self, client) -> None:
        """超上限返回 422 单一 detail，而不是端点内 ValidationError 的 500。"""
        response = client.get("/api/v1/hotspot/?page=1&page_size=501")
        assert response.status_code == 422
        assert "detail" in response.json()
