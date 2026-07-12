from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestStocksEndpoints:
    def test_search_stocks(self, client) -> None:
        mock_items = [
            type(
                "StockBasic",
                (object,),
                {
                    "stock_code": "000001",
                    "stock_name": "平安银行",
                    "market": "sz",
                    "industry_l1": "银行",
                    "industry_l2": "股份制银行",
                    "industry_l3": "银行III",
                    "listing_date": None,
                },
            )()
        ]

        with patch("app.api.v1.stocks.stock_service.search_stocks", return_value=mock_items):
            response = client.get("/api/v1/stocks/search?q=000001")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["stock_code"] == "000001"

    def test_get_stock_not_found(self, client) -> None:
        with patch("app.api.v1.stocks.stock_service.get_stock_by_code", return_value=None):
            response = client.get("/api/v1/stocks/999999")

        assert response.status_code == 404
