"""paper-trade sidecar HTTP 客户端（薄封装：HTTP 往返 + 异常翻译）。

契约由 ``docker/paper-trade/main.py`` 定义（内网协议，柜台报文原样透传，
symbol 用掘金格式 SHSE.600000）。短连接：调用频度低（盘后同步 + 盘中轮询 +
页面按需查询），免长连接生命周期管理（同 douyin signer 先例）。
本模块只做「HTTP 往返 + 异常翻译」，不落库、不持状态。
"""

from typing import Any

import httpx

from app.core.config import get_settings
from app.services.trading.errors import PaperTradeGatewayError, PaperTradeNotConfiguredError


def _detail(response: httpx.Response) -> str:
    """sidecar 错误体形如 {detail: msg}；解析失败回退原文截断。"""
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(payload, dict) and payload.get("detail"):
        return str(payload["detail"])[:200]
    return response.text[:200]


class PaperTradeClient:
    """掘金仿真 sidecar 客户端（``transport`` 参数供测试注入）。"""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds: float = (
            timeout_seconds
            if timeout_seconds is not None
            else get_settings().paper_trade_timeout
        )
        self._transport = transport

    async def _request(
        self, method: str, path: str, *, json_body: Any | None = None
    ) -> Any:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.request(
                    method, f"{self._base_url}{path}", json=json_body
                )
        except httpx.HTTPError as exc:
            raise PaperTradeGatewayError(f"模拟盘网关不可达: {exc}") from exc
        if response.status_code == 503:
            # sidecar 503 = 凭据缺失/无效（GMTRADE_TOKEN 等），同属"未配置"语义
            raise PaperTradeNotConfiguredError(_detail(response))
        if response.status_code >= 400:
            raise PaperTradeGatewayError(_detail(response))
        try:
            return response.json()
        except ValueError as exc:
            raise PaperTradeGatewayError(
                f"模拟盘网关返回非 JSON: {response.text[:200]}"
            ) from exc

    async def get_cash(self) -> Any:
        """资金概况（nav/available/balance/cum_inout/last_inout 等）。"""
        return await self._request("GET", "/cash")

    async def get_positions(self) -> Any:
        """当前持仓列表。"""
        return await self._request("GET", "/positions")

    async def get_intraday_orders(self) -> Any:
        """当日委托列表（盘后同步数据源）。"""
        return await self._request("GET", "/orders")

    async def get_unfinished_orders(self) -> Any:
        """未结委托列表。"""
        return await self._request("GET", "/orders/unfinished")

    async def get_intraday_executions(self) -> Any:
        """当日成交回报列表（盘后同步数据源）。"""
        return await self._request("GET", "/orders/executions")

    async def place_order(
        self,
        symbol: str,
        side: str,
        volume: int,
        *,
        price: float = 0.0,
        order_type: str = "limit",
    ) -> Any:
        """下单（限价单必须带价格，由 sidecar 校验；拒单透传柜台原因）。"""
        return await self._request(
            "POST",
            "/orders",
            json_body={
                "symbol": symbol,
                "side": side,
                "volume": volume,
                "order_type": order_type,
                "price": price,
            },
        )

    async def cancel_order(self, cl_ord_id: str) -> Any:
        """按柜台委托号撤单。"""
        return await self._request("DELETE", f"/orders/{cl_ord_id}")

    async def cancel_all(self) -> Any:
        """撤销全部未结委托。"""
        return await self._request("DELETE", "/orders")
