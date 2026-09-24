"""paper-trade sidecar 客户端契约测试（透传 / 异常翻译 / 报文形状）。"""

import httpx
import pytest

from app.services.trading.client import PaperTradeClient
from app.services.trading.errors import (
    PaperTradeGatewayError,
    PaperTradeNotConfiguredError,
)

_BASE = "http://paper-trade:8020/"


def _client(handler) -> PaperTradeClient:
    return PaperTradeClient(
        _BASE, timeout_seconds=1.0, transport=httpx.MockTransport(handler)
    )


@pytest.mark.unit
class TestPaperTradeClient:
    @pytest.mark.asyncio
    async def test_get_cash_passthrough(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/cash"
            return httpx.Response(200, json={"nav": 100000.0})

        assert await _client(handler).get_cash() == {"nav": 100000.0}

    @pytest.mark.asyncio
    async def test_get_intraday_executions_path(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/orders/executions"
            return httpx.Response(200, json=[])

        assert await _client(handler).get_intraday_executions() == []

    @pytest.mark.asyncio
    async def test_place_order_body_shape(self) -> None:
        import json

        payload_seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/orders"
            payload_seen.update(json.loads(request.read()))
            return httpx.Response(200, json=[{"cl_ord_id": "abc"}])

        result = await _client(handler).place_order(
            "SHSE.600000", "buy", 100, price=12.34
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
    async def test_503_maps_to_not_configured(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "GMTRADE_TOKEN 未配置"})

        with pytest.raises(PaperTradeNotConfiguredError, match="GMTRADE_TOKEN"):
            await _client(handler).get_cash()

    @pytest.mark.asyncio
    async def test_502_maps_to_gateway_error_with_detail(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, json={"detail": "仿真柜台返回 500: boom"})

        with pytest.raises(PaperTradeGatewayError, match="boom"):
            await _client(handler).get_cash()

    @pytest.mark.asyncio
    async def test_transport_error_maps_to_gateway_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with pytest.raises(PaperTradeGatewayError, match="不可达"):
            await _client(handler).get_cash()

    @pytest.mark.asyncio
    async def test_non_json_response_maps_to_gateway_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>proxy error</html>")

        with pytest.raises(PaperTradeGatewayError, match="非 JSON"):
            await _client(handler).get_cash()
