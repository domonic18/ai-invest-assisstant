"""签名 sidecar HTTP 客户端：POST /sign 往返与异常归类（transport 的 signer SEAM）。

契约与 ``app/signer/models.py`` 对齐（内网协议，snake 原生形状）。本模块只做
「HTTP 往返 + 异常翻译」，决策（回退、是否冷却 jar）在 transport 的降级矩阵。
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class SignerUnavailableError(RuntimeError):
    """sidecar 不可达/浏览器未就绪（连接失败、超时、503）——基础设施问题。"""


class SignerRejectedError(RuntimeError):
    """sidecar 在线但拒绝/无法签名（422/502、空参数、回显 UA 不一致）。"""


class DouyinSignerProtocol(Protocol):
    """transport 依赖的最小签名面（测试注入 fake signer）。"""

    async def sign(
        self, path: str, query: str, user_agent: str, cookies: str
    ) -> dict[str, str]: ...


class DouyinSignerClient:
    """zjz douyin-signer 客户端（短连接：签名频度低，免长连接生命周期管理）。"""

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
            else get_settings().douyin_signer_timeout
        )
        self._transport = transport

    async def sign(
        self, path: str, query: str, user_agent: str, cookies: str
    ) -> dict[str, str]:
        """请 sidecar 以本 jar 身份签名，返回页面 SDK 追加的参数（原样）。"""
        payload = {
            "path": path,
            "query": query,
            "user_agent": user_agent,
            "cookies": cookies,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(f"{self._base_url}/sign", json=payload)
        except httpx.HTTPError as exc:
            raise SignerUnavailableError(f"签名服务不可达: {exc}") from exc
        if response.status_code == 503:
            raise SignerUnavailableError("签名服务浏览器未就绪")
        if response.status_code == 502:
            raise SignerRejectedError(f"签名页失败: {response.text[:200]}")
        if response.status_code != 200:
            raise SignerRejectedError(f"签名服务拒绝（HTTP {response.status_code}）")
        try:
            data = response.json()
        except ValueError as exc:
            raise SignerRejectedError(
                f"签名服务返回非 JSON 响应: {response.text[:200]}"
            ) from exc
        params = data.get("params")
        if not isinstance(params, dict) or not params:
            raise SignerRejectedError("签名服务返回空参数")
        if data.get("user_agent") != user_agent:
            raise SignerRejectedError("签名服务回显 UA 不一致")
        return {str(k): str(v) for k, v in params.items()}

    async def health(self) -> dict[str, Any]:
        """探测 /health（admin status 用；不可达抛 SignerUnavailableError）。"""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.get(f"{self._base_url}/health")
        except httpx.HTTPError as exc:
            raise SignerUnavailableError(f"签名服务不可达: {exc}") from exc
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            # 200 但非 JSON（如代理返回 HTML）视同基础设施不可达
            raise SignerUnavailableError(
                f"签名服务响应非 JSON: {response.text[:200]}"
            ) from exc
        return payload


def build_signer(url: str | None) -> DouyinSignerClient | None:
    """URL 为空即禁用（全链路零改动回退本地 a_bogus）。"""
    if not url:
        return None
    return DouyinSignerClient(url)
