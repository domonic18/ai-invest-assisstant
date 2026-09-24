"""模拟盘 API 契约测试（未配置引导卡 / camelCase wire / 账户维度 / 403 / 鉴权）。"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ForbiddenError
from app.models.paper_trade import PaperTradeOrder
from app.services.trading.errors import PaperTradeNotConfiguredError

_TRADE_DATE = date(2026, 9, 24)
_ACCOUNT_ID = 11


def _stub_account(**overrides: object) -> SimpleNamespace:
    payload = {
        "id": _ACCOUNT_ID,
        "user_id": 1,
        "name": "人工盘",
        "counter_account_id": "acc-1",
        "is_agent": False,
        "is_enabled": True,
        "token_encrypted": "gAAAA-encrypted",
        "last_error": None,
        "last_synced_at": None,
        "created_at": datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _resolve(account: SimpleNamespace) -> AsyncMock:
    return AsyncMock(return_value=account)


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
        "order_source": "manual",
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
        assert client.get("/api/v1/paper-trade/accounts").status_code in (401, 403)

    def test_overview_not_configured_returns_guide_payload(self, user_client) -> None:
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.get_overview",
                AsyncMock(side_effect=PaperTradeNotConfiguredError()),
            ),
        ):
            resp = user_client.get(
                "/api/v1/paper-trade/overview", params={"account_id": _ACCOUNT_ID}
            )

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
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.get_overview",
                AsyncMock(return_value=payload),
            ),
        ):
            resp = user_client.get(
                "/api/v1/paper-trade/overview", params={"account_id": _ACCOUNT_ID}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert body["cash"]["nav"] == 200000.0
        assert body["positions"][0]["stockCode"] == "600000"
        unfinished = body["unfinishedOrders"][0]
        assert unfinished["clOrdId"] == "u1"
        assert unfinished["tradeDate"] == "2026-09-24"

    def test_orders_requires_account_id(self, user_client) -> None:
        resp = user_client.get("/api/v1/paper-trade/orders")
        assert resp.status_code == 422

    def test_orders_paginates_local_table(self, user_client) -> None:
        rows = [_order_row(), _order_row(cl_ord_id="o2")]
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.get_orders",
                AsyncMock(return_value=(rows, _TRADE_DATE, 2)),
            ) as svc_mock,
        ):
            resp = user_client.get(
                "/api/v1/paper-trade/orders",
                params={
                    "account_id": _ACCOUNT_ID,
                    "trade_date": _TRADE_DATE.isoformat(),
                    "page": 2,
                    "page_size": 50,
                },
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
        assert args[1] == _ACCOUNT_ID
        assert args[2] == _TRADE_DATE
        assert args[3] == 2
        assert args[4] == 50

    def test_orders_rejects_invalid_page_size(self, user_client) -> None:
        resp = user_client.get(
            "/api/v1/paper-trade/orders",
            params={"account_id": _ACCOUNT_ID, "page_size": 0},
        )
        assert resp.status_code == 422

    def test_executions_maps_wire(self, user_client) -> None:
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
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.get_executions",
                AsyncMock(return_value=([row], _TRADE_DATE, 1)),
            ),
        ):
            resp = user_client.get(
                "/api/v1/paper-trade/executions",
                params={"account_id": _ACCOUNT_ID},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tradeDate"] == "2026-09-24"
        assert body["items"][0]["execId"] == "e1"
        assert body["items"][0]["turnover"] == 850.0

    def test_executions_turnover_fallback_for_legacy_rows(self, user_client) -> None:
        """存量回报行无成交额：wire 层按 价×量 补算（回报不可变无法回填）。"""
        row = SimpleNamespace(
            exec_id="e2",
            cl_ord_id="o2",
            trade_date=_TRADE_DATE,
            symbol="SZSE.002520",
            side=1,
            exec_type=15,
            price=6.47,
            volume=4000,
            turnover=None,
            commission=None,
            counter_created_at=datetime(2026, 9, 24, 7, 2, tzinfo=timezone.utc),
        )
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.get_executions",
                AsyncMock(return_value=([row], _TRADE_DATE, 1)),
            ),
        ):
            resp = user_client.get(
                "/api/v1/paper-trade/executions",
                params={"account_id": _ACCOUNT_ID},
            )

        assert resp.status_code == 200
        assert resp.json()["items"][0]["turnover"] == 25880.0  # 6.47*4000

    def test_nav_returns_ascending_points(self, user_client) -> None:
        rows = [
            SimpleNamespace(trade_date=date(2026, 9, 23), nav=199000.0, available=1000.0),
            SimpleNamespace(trade_date=date(2026, 9, 24), nav=200000.0, available=2000.0),
        ]
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.get_nav_history",
                AsyncMock(return_value=rows),
            ) as svc_mock,
        ):
            resp = user_client.get(
                "/api/v1/paper-trade/nav",
                params={"account_id": _ACCOUNT_ID, "days": 10},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert [point["tradeDate"] for point in body["items"]] == [
            "2026-09-23",
            "2026-09-24",
        ]
        assert body["items"][1]["nav"] == 200000.0
        args, _kwargs = svc_mock.await_args
        assert args[1] == _ACCOUNT_ID
        assert args[2] == 10


@pytest.mark.unit
class TestPaperTradeAccountsApi:
    def test_list_accounts_masks_token(self, user_client) -> None:
        account = _stub_account()
        with (
            patch(
                "app.api.v1.paper_trade.account_service.list_accounts",
                AsyncMock(return_value=[account]),
            ),
            patch(
                "app.api.v1.paper_trade.decrypt_token",
                lambda cipher: "tok-secret-1234",
            ),
        ):
            resp = user_client.get("/api/v1/paper-trade/accounts")

        assert resp.status_code == 200
        row = resp.json()["items"][0]
        assert row["name"] == "人工盘"
        assert row["counterAccountId"] == "acc-1"
        assert row["tokenMasked"].startswith("tok-")
        assert "secret" not in row["tokenMasked"]
        assert row["isAgent"] is False

    def test_create_account_returns_201(self, user_client) -> None:
        created = _stub_account(id=12, name="agent 盘", is_agent=True)
        with (
            patch(
                "app.api.v1.paper_trade.account_service.create_account",
                AsyncMock(return_value=created),
            ) as svc_mock,
            patch(
                "app.api.v1.paper_trade.decrypt_token",
                lambda cipher: "tok-secret-1234",
            ),
        ):
            resp = user_client.post(
                "/api/v1/paper-trade/accounts",
                json={
                    "name": "agent 盘",
                    "token": "tok",
                    "counterAccountId": "acc-2",
                },
            )

        assert resp.status_code == 201
        assert resp.json()["id"] == 12
        kwargs = svc_mock.call_args.kwargs
        assert kwargs["name"] == "agent 盘"
        assert kwargs["counter_account_id"] == "acc-2"

    def test_delete_account_returns_204(self, user_client) -> None:
        with patch(
            "app.api.v1.paper_trade.account_service.delete_account",
            AsyncMock(return_value=None),
        ):
            resp = user_client.delete("/api/v1/paper-trade/accounts/11")
        assert resp.status_code == 204


@pytest.mark.unit
class TestPaperTradeManualTradingApi:
    def test_place_order_returns_cl_ord_id(self, user_client) -> None:
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.place_order",
                AsyncMock(return_value=[{"cl_ord_id": "n1", "status": 1}]),
            ) as svc_mock,
        ):
            resp = user_client.post(
                "/api/v1/paper-trade/orders",
                json={
                    "accountId": _ACCOUNT_ID,
                    "symbol": "SHSE.600000",
                    "side": "buy",
                    "volume": 100,
                    "orderType": "limit",
                    "price": 8.5,
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["clOrdId"] == "n1"
        kwargs = svc_mock.call_args.kwargs
        assert kwargs["symbol"] == "SHSE.600000"
        assert kwargs["side"] == "buy"

    def test_place_order_rejected_on_agent_account(self, user_client) -> None:
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account(is_agent=True)),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.place_order",
                AsyncMock(side_effect=ForbiddenError("agent 专属账户禁止人工操作")),
            ),
        ):
            resp = user_client.post(
                "/api/v1/paper-trade/orders",
                json={
                    "accountId": _ACCOUNT_ID,
                    "symbol": "SHSE.600000",
                    "side": "buy",
                    "volume": 100,
                },
            )

        assert resp.status_code == 403

    def test_cancel_order_returns_action(self, user_client) -> None:
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.cancel_order",
                AsyncMock(return_value={}),
            ),
        ):
            resp = user_client.delete(
                "/api/v1/paper-trade/orders/o1",
                params={"account_id": _ACCOUNT_ID},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["clOrdId"] == "o1"

    def test_sync_account_returns_summary(self, user_client) -> None:
        with (
            patch(
                "app.api.v1.paper_trade.account_service.resolve_for_user",
                _resolve(_stub_account()),
            ),
            patch(
                "app.api.v1.paper_trade.paper_trade_service.sync_account_now",
                AsyncMock(
                    return_value={
                        "trade_date": "2026-09-24",
                        "account_id": _ACCOUNT_ID,
                        "orders": 2,
                        "executions": 1,
                        "nav": 199105.0,
                    }
                ),
            ),
        ):
            resp = user_client.post(f"/api/v1/paper-trade/accounts/{_ACCOUNT_ID}/sync")

        assert resp.status_code == 200
        body = resp.json()
        assert body["tradeDate"] == "2026-09-24"
        assert body["accountId"] == _ACCOUNT_ID
        assert body["orders"] == 2
        assert body["executions"] == 1
