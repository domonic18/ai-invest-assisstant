"""paper-trade sidecar 客户端契约测试（透传 / 凭证头 / 通道密钥 / 异常翻译 / 报文形状）。"""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.services.trading.client import CounterCredentials, PaperTradeClient
from app.services.trading.errors import (
    PaperTradeGatewayError,
    PaperTradeNotConfiguredError,
    PaperTradeTokenInvalidError,
)

_BASE = "http://paper-trade:8020/"
_CRED = CounterCredentials(token="tok-1", account_id="acc-1")


def _client(handler) -> PaperTradeClient:
    return PaperTradeClient(
        _BASE, timeout_seconds=1.0, transport=httpx.MockTransport(handler)
    )


def _assert_headers(request: httpx.Request) -> None:
    assert request.headers["x-gm-token"] == "tok-1"
    assert request.headers["x-gm-account-id"] == "acc-1"


@pytest.mark.unit
class TestPaperTradeClient:
    @pytest.mark.asyncio
    async def test_get_cash_passthrough(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/cash"
            _assert_headers(request)
            return httpx.Response(200, json={"nav": 100000.0})

        assert await _client(handler).get_cash(_CRED) == {"nav": 100000.0}

    @pytest.mark.asyncio
    async def test_get_intraday_executions_path(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/orders/executions"
            return httpx.Response(200, json=[])

        assert await _client(handler).get_intraday_executions(_CRED) == []

    @pytest.mark.asyncio
    async def test_place_order_body_shape(self) -> None:
        payload_seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/orders"
            payload_seen.update(json.loads(request.read()))
            return httpx.Response(200, json=[{"cl_ord_id": "abc"}])

        result = await _client(handler).place_order(
            _CRED, "SHSE.600000", "buy", 100, price=12.34
        )

        assert result == [{"cl_ord_id": "abc"}]
        assert payload_seen == {
            "symbol": "SHSE.600000",
            "side": "buy",
            "volume": 100,
            "order_type": "limit",
            "price": 12.34,
        }

    @pytest.mark.asyncio
    async def test_400_maps_to_gateway_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"detail": "缺少 X-Gm-Token 请求头"})

        with pytest.raises(PaperTradeGatewayError, match="X-Gm-Token"):
            await _client(handler).get_cash(_CRED)

    @pytest.mark.asyncio
    async def test_shared_secret_header_added_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.trading.client.get_settings",
            lambda: SimpleNamespace(paper_trade_shared_secret="sec-1"),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["x-shared-secret"] == "sec-1"
            return httpx.Response(200, json={"nav": 1.0})

        assert await _client(handler).get_cash(_CRED) == {"nav": 1.0}

    @pytest.mark.asyncio
    async def test_shared_secret_header_absent_when_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.trading.client.get_settings",
            lambda: SimpleNamespace(paper_trade_shared_secret=""),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert "x-shared-secret" not in request.headers
            return httpx.Response(200, json={})

        assert await _client(handler).get_cash(_CRED) == {}

    @pytest.mark.asyncio
    async def test_503_maps_to_not_configured(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "模拟盘功能未配置"})

        with pytest.raises(PaperTradeNotConfiguredError, match="未配置"):
            await _client(handler).get_cash(_CRED)

    @pytest.mark.asyncio
    async def test_503_token_invalid_maps_to_token_invalid_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                503, json={"detail": "掘金仿真 token 无效（sim.myquant.cn 个人中心可重置）"}
            )

        # 细分子类，同时保持 NotConfigured 语义（引导卡行为不变）
        with pytest.raises(PaperTradeTokenInvalidError, match="token 无效"):
            await _client(handler).get_cash(_CRED)

    @pytest.mark.asyncio
    async def test_502_maps_to_gateway_error_with_detail(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, json={"detail": "仿真柜台返回 500: boom"})

        with pytest.raises(PaperTradeGatewayError, match="boom"):
            await _client(handler).get_cash(_CRED)

    @pytest.mark.asyncio
    async def test_transport_error_maps_to_gateway_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with pytest.raises(PaperTradeGatewayError, match="不可达"):
            await _client(handler).get_cash(_CRED)

    @pytest.mark.asyncio
    async def test_non_json_response_maps_to_gateway_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>proxy error</html>")

        with pytest.raises(PaperTradeGatewayError, match="非 JSON"):
            await _client(handler).get_cash(_CRED)
