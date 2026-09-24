"""模拟盘 API 契约测试（未配置引导卡 / camelCase wire / 分页与鉴权）。"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.paper_trade import PaperTradeOrder
from app.services.trading.errors import PaperTradeNotConfiguredError

_TRADE_DATE = date(2026, 9, 24)


def _order_row(**overrides: object) -> PaperTradeOrder:
    payload = {
        "cl_ord_id": "o1",
        "trade_date": _TRADE_DATE,
        "symbol": "SHSE.600000",
        "stock_code": "600000",
        "side": 1,
        "order_type": 1,
        "position_effect": 1,
        "price": 8.5,
        "volume": 100,
        "status": 5,
        "counter_created_at": datetime(2026, 9, 24, 7, 1, tzinfo=timezone.utc),
    }
    payload.update(overrides)
    return PaperTradeOrder(**payload)


@pytest.mark.unit
class TestPaperTradeApi:
    def test_requires_auth(self, client) -> None:
        assert client.get("/api/v1/paper-trade/overview").status_code in (401, 403)
        assert client.get("/api/v1/paper-trade/orders").status_code in (401, 403)
        assert client.get("/api/v1/paper-trade/executions").status_code in (401, 403)
        assert client.get("/api/v1/paper-trade/nav").status_code in (401, 403)

    def test_overview_not_configured_returns_guide_payload(self, user_client) -> None:
        with patch(
            "app.api.v1.paper_trade.paper_trade_service.get_overview",
            AsyncMock(side_effect=PaperTradeNotConfiguredError()),
        ):
            resp = user_client.get("/api/v1/paper-trade/overview")

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "enabled": False,
            "cash": None,
            "positions": [],
            "unfinishedOrders": [],
        }

    def test_overview_maps_counter_payload(self, user_client) -> None:
        payload = {
            "enabled": True,
            "cash": {"nav": 200000.0, "available": 198000.0},
            "positions": [
                {"symbol": "SHSE.600000", "stock_code": "600000", "volume": 100}
            ],
            "unfinished_orders": [
                {
                    "cl_ord_id": "u1",
                    "trade_date": _TRADE_DATE,
                    "symbol": "SZSE.000001",
                    "stock_code": "000001",
                    "side": 1,
                    "order_type": 1,
                    "position_effect": 1,
                    "price": 12.0,
                    "volume": 200,
                    "status": 1,
                }
            ],
        }
        with patch(
            "app.api.v1.paper_trade.paper_trade_service.get_overview",
            AsyncMock(return_value=payload),
        ):
            resp = user_client.get("/api/v1/paper-trade/overview")

        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert body["cash"]["nav"] == 200000.0
        assert body["positions"][0]["stockCode"] == "600000"
        unfinished = body["unfinishedOrders"][0]
        assert unfinished["clOrdId"] == "u1"
        assert unfinished["tradeDate"] == "2026-09-24"

    def test_orders_paginates_local_table(self, user_client) -> None:
        rows = [_order_row(), _order_row(cl_ord_id="o2")]
        with patch(
            "app.api.v1.paper_trade.paper_trade_service.get_orders",
            AsyncMock(return_value=(rows, _TRADE_DATE, 2)),
        ) as svc_mock:
            resp = user_client.get(
                "/api/v1/paper-trade/orders",
                params={"trade_date": _TRADE_DATE.isoformat(), "page": 2, "page_size": 50},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 2
        assert body["pageSize"] == 50
        assert body["tradeDate"] == "2026-09-24"
        assert [item["clOrdId"] for item in body["items"]] == ["o1", "o2"]
        assert body["items"][0]["counterCreatedAt"].startswith("2026-09-24T07:01:00")
        args, _kwargs = svc_mock.await_args
        assert args[1] == _TRADE_DATE
        assert args[2] == 2
        assert args[3] == 50

    def test_orders_rejects_invalid_page_size(self, user_client) -> None:
        resp = user_client.get("/api/v1/paper-trade/orders", params={"page_size": 0})
        assert resp.status_code == 422

    def test_executions_maps_wire(self, user_client) -> None:
        from types import SimpleNamespace

        row = SimpleNamespace(
            exec_id="e1",
            cl_ord_id="o1",
            trade_date=_TRADE_DATE,
            symbol="SHSE.600000",
            side=1,
            exec_type=15,
            price=8.5,
            volume=100,
            turnover=850.0,
            commission=0.85,
            counter_created_at=datetime(2026, 9, 24, 7, 2, tzinfo=timezone.utc),
        )
        with patch(
            "app.api.v1.paper_trade.paper_trade_service.get_executions",
            AsyncMock(return_value=([row], _TRADE_DATE, 1)),
        ):
            resp = user_client.get("/api/v1/paper-trade/executions")

        assert resp.status_code == 200
        body = resp.json()
        assert body["tradeDate"] == "2026-09-24"
        assert body["items"][0]["execId"] == "e1"
        assert body["items"][0]["turnover"] == 850.0

    def test_nav_returns_ascending_points(self, user_client) -> None:
        from types import SimpleNamespace

        rows = [
            SimpleNamespace(trade_date=date(2026, 9, 23), nav=199000.0, available=1000.0),
            SimpleNamespace(trade_date=date(2026, 9, 24), nav=200000.0, available=2000.0),
        ]
        with patch(
            "app.api.v1.paper_trade.paper_trade_service.get_nav_history",
            AsyncMock(return_value=rows),
        ) as svc_mock:
            resp = user_client.get("/api/v1/paper-trade/nav", params={"days": 10})

        assert resp.status_code == 200
        body = resp.json()
        assert [point["tradeDate"] for point in body["items"]] == [
            "2026-09-23",
            "2026-09-24",
        ]
        assert body["items"][1]["nav"] == 200000.0
        args, _kwargs = svc_mock.await_args
        assert args[1] == 10
