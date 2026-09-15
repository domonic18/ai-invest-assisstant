"""抖音 Web API 传输层：curl_cffi Chrome TLS 指纹 + Cookie jar 轮换 + a_bogus 签名。

东财同款 WAF 生态按 TLS 指纹拦截，必须走 curl_cffi 的 Chrome 指纹
（先例见 collector/spiders/eastmoney_research_report.py）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, cast

from app.adapters.douyin.exceptions import (
    RiskControlError,
    SignatureError,
    StructureDriftError,
)
from app.adapters.douyin.signing import (
    DEFAULT_USER_AGENT,
    ABogus,
    generate_fingerprint,
)

DOUYIN_BASE_URL = "https://www.douyin.com"

REQUEST_TIMEOUT_SECONDS = 15.0

# 命中即按风控处置的 HTTP 状态与特征
_RISK_CONTROL_STATUSES = {403, 429}
_RISK_CONTROL_BODY_MARKERS = ("captcha", "verify", "安全验证")

# jar 冷却：指数退避（分钟级），上限 2 小时
_JAR_COOL_DOWN_BASE_SECONDS = 300
_JAR_COOL_DOWN_MAX_SECONDS = 7200


class _AsyncHttpSession(Protocol):
    """curl_cffi AsyncSession 的最小鸭子类型（测试注入 fake 会话）。"""

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        allow_redirects: bool = True,
    ) -> Any: ...

    async def __aenter__(self) -> _AsyncHttpSession: ...

    async def __aexit__(self, *args: Any) -> None: ...


def _default_session_factory() -> _AsyncHttpSession:
    from curl_cffi.requests import AsyncSession

    session: Any = AsyncSession(impersonate="chrome")
    return cast("_AsyncHttpSession", session)


@dataclass
class _CookieJar:
    """一份 Cookie 身份；命中风控后按指数退避冷却。"""

    cookie: str
    cool_until: datetime | None = None
    strikes: int = 0

    def is_available(self, now: datetime) -> bool:
        return self.cool_until is None or self.cool_until <= now

    def cool_down(self) -> None:
        self.strikes += 1
        seconds = min(
            _JAR_COOL_DOWN_BASE_SECONDS * (2 ** (self.strikes - 1)),
            _JAR_COOL_DOWN_MAX_SECONDS,
        )
        self.cool_until = datetime.now(timezone.utc) + timedelta(seconds=seconds)

    def revive(self) -> None:
        """请求成功后重置退避。"""
        self.strikes = 0
        self.cool_until = None


class DouyinTransport:
    """有状态传输会话：UA/指纹与签名绑定，多 jar 轮换，命中风控自动冷却。"""

    def __init__(
        self,
        cookies: list[str] | None = None,
        user_agent: str | None = None,
        fingerprint: str | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self._user_agent = user_agent or DEFAULT_USER_AGENT
        self._fingerprint = fingerprint or generate_fingerprint()
        self._abogus = ABogus(
            user_agent=self._user_agent, fp=self._fingerprint, options=[0, 1, 8]
        )
        self._session_factory = session_factory or _default_session_factory
        self._jars: list[_CookieJar] = [_CookieJar(c) for c in (cookies or [])]
        self._cursor = 0

    @property
    def user_agent(self) -> str:
        return self._user_agent

    @property
    def jars_available(self) -> int:
        now = datetime.now(timezone.utc)
        return sum(1 for jar in self._jars if jar.is_available(now))

    @property
    def jars_total(self) -> int:
        return len(self._jars)

    def replace_jars(self, cookies: list[str]) -> None:
        """整体替换 jar 池（自举/手动导入后调用）。"""
        self._jars = [_CookieJar(c) for c in cookies]
        self._cursor = 0

    def _next_available_jar(self) -> _CookieJar:
        now = datetime.now(timezone.utc)
        total = len(self._jars)
        for offset in range(total):
            jar = self._jars[(self._cursor + offset) % total]
            if jar.is_available(now):
                self._cursor = (self._cursor + offset + 1) % total
                return jar
        raise RiskControlError(
            f"无可用 Cookie jar（共 {total} 份，全部冷却或未配置）"
        )

    def _headers(self, jar: _CookieJar) -> dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Referer": f"{DOUYIN_BASE_URL}/",
            "Accept": "application/json, text/plain, */*",
            "Cookie": jar.cookie,
        }

    async def get_json(self, path: str, params: str) -> dict[str, Any]:
        """签名并请求 GET 接口。

        Args:
            path: 接口路径（如 ``/aweme/v1/web/aweme/post/``）。
            params: 原始 query 串（调用方保证已 urlencode）。

        Returns:
            服务端 JSON 响应。

        Raises:
            RiskControlError: 403/429/captcha/频控。
            SignatureError: 400 或签名被拒。
            StructureDriftError: 2xx 但响应非 JSON。
        """
        jar = self._next_available_jar()
        signed_params = self._abogus.generate_abogus(params)[0]
        url = f"{DOUYIN_BASE_URL}{path}?{signed_params}"

        async with self._session_factory() as session:
            response = await session.get(
                url,
                headers=self._headers(jar),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

        status = getattr(response, "status_code", 0)
        text = getattr(response, "text", "") or ""
        if status in _RISK_CONTROL_STATUSES or any(
            marker in text for marker in _RISK_CONTROL_BODY_MARKERS
        ):
            jar.cool_down()
            raise RiskControlError(f"HTTP {status}: {text[:200]}")
        if status == 400:
            raise SignatureError(f"HTTP 400: {text[:200]}")
        if status < 200 or status >= 300:
            jar.cool_down()
            raise RiskControlError(f"HTTP {status}: {text[:200]}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StructureDriftError(f"响应非 JSON（HTTP {status}）: {text[:200]}") from exc
        if not isinstance(data, dict):
            raise StructureDriftError(f"响应顶层不是对象（HTTP {status}）")
        return data

    async def resolve_redirect(self, url: str) -> str:
        """跟随一次 302 取最终地址（分享短链展开用，不带 Cookie 不签名）。"""
        async with self._session_factory() as session:
            response = await session.get(
                url,
                headers={"User-Agent": self._user_agent},
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        location = response.headers.get("Location") if hasattr(response, "headers") else None
        if not location:
            raise StructureDriftError(f"短链未返回跳转目标: {url}")
        return str(location)
