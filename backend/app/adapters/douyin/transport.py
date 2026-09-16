"""抖音 Web API 传输层：curl_cffi Chrome TLS 指纹 + Cookie jar 轮换 + 签名。

东财同款 WAF 生态按 TLS 指纹拦截，必须走 curl_cffi 的 Chrome 指纹
（先例见 collector/spiders/eastmoney_research_report.py）。
签名双轨：signer（页面 SDK sidecar）在线用其参数原样透传，失败/未配置
回退本地 a_bogus（灰度期端点仍可用）。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, cast
from urllib.parse import urlencode

import structlog

from app.adapters.douyin.exceptions import (
    RiskControlError,
    SignatureError,
    StructureDriftError,
)
from app.adapters.douyin.signer_client import (
    DouyinSignerProtocol,
    SignerRejectedError,
    SignerUnavailableError,
)
from app.adapters.douyin.signing import (
    DEFAULT_USER_AGENT,
    ABogus,
    generate_fingerprint,
)

logger = structlog.get_logger(__name__)

DOUYIN_BASE_URL = "https://www.douyin.com"

REQUEST_TIMEOUT_SECONDS = 15.0

# 命中即按风控处置的 HTTP 状态；正文特征只对 2xx 非 JSON（验证页 HTML）检查
_RISK_CONTROL_STATUSES = {403, 429}
_RISK_CONTROL_BODY_MARKERS = ("captcha", "verify", "安全验证")

# Argus 门禁确定性拒绝（2026-09-14 起灰度覆盖作品端点）：重试只会加速验证码
_ARGUS_REJECTION_MARKER = "ArgusSecurityPlugin"

# 限速型 403/429 与 200 空 body 是瞬时的（douyin-downloader 实测同 cookie
# 秒级恢复）：冷却会杀死秒级重试，sleep 后换 jar 重签重发
_RATE_LIMIT_RETRY_DELAYS: tuple[float, ...] = (1.0, 2.0, 5.0)

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
        signer: DouyinSignerProtocol | None = None,
        rate_limit_retry_delays: tuple[float, ...] = _RATE_LIMIT_RETRY_DELAYS,
    ) -> None:
        self._user_agent = user_agent or DEFAULT_USER_AGENT
        self._fingerprint = fingerprint or generate_fingerprint()
        self._abogus = ABogus(
            user_agent=self._user_agent, fp=self._fingerprint, options=[0, 1, 8]
        )
        self._session_factory = session_factory or _default_session_factory
        self._signer = signer
        self._retry_delays = rate_limit_retry_delays
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
        """签名并请求 GET 接口（限速瞬时失败重签重试，Argus 门禁立即终态）。

        Args:
            path: 接口路径（如 ``/aweme/v1/web/aweme/post/``）。
            params: 原始 query 串（调用方保证已 urlencode）。

        Returns:
            服务端 JSON 响应。

        Raises:
            RiskControlError: Argus 拒绝/captcha/5xx/限速与空 body 重试耗尽。
            SignatureError: 400（签名被拒）。
            StructureDriftError: 2xx 但响应非 JSON。
        """
        last_body = ""
        for attempt in range(len(self._retry_delays) + 1):
            jar = self._next_available_jar()
            url = f"{DOUYIN_BASE_URL}{path}?{await self._sign(path, params, jar)}"

            async with self._session_factory() as session:
                response = await session.get(
                    url,
                    headers=self._headers(jar),
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

            status = getattr(response, "status_code", 0)
            text = getattr(response, "text", "") or ""
            if status < 200 or status >= 300:
                # 通道级失败的现场记录（url/status/响应头），便于归因风控形态
                logger.warning(
                    "social_douyin_request_rejected",
                    path=path,
                    status=status,
                    body=text[:160],
                )
            if status == 400:
                raise SignatureError(f"HTTP 400: {text[:200]}")
            if status not in _RISK_CONTROL_STATUSES and not 200 <= status < 300:
                jar.cool_down()
                raise RiskControlError(f"HTTP {status}: {text[:200]}")
            if status in _RISK_CONTROL_STATUSES:
                if _ARGUS_REJECTION_MARKER in text:
                    jar.cool_down()
                    raise RiskControlError(f"HTTP {status}: {text[:200]}")
                # 限速型（body 空或无关）：不冷却，换 jar 重签重发
                last_body = text
            elif not text.strip():
                # 200 空 body = 反爬扣发/身份不一致，重签重发（计入同一预算）
                last_body = text
            else:
                data = self._parse_json(status, text, jar)
                jar.revive()
                return data
            if attempt < len(self._retry_delays):
                await asyncio.sleep(self._retry_delays[attempt])
        raise RiskControlError(
            f"限速/扣发重试耗尽（{len(self._retry_delays) + 1} 次）: {last_body[:200]}"
        )

    def _parse_json(self, status: int, text: str, jar: _CookieJar) -> dict[str, Any]:
        """解析 2xx body；验证页 HTML 判风控（jar 冷却），其余非 JSON 判结构漂移。"""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            # 2xx 非 JSON 才可能是风控验证页；成功 JSON 内含 verify 等词属正常字段
            # （2026-09-16 走查：aweme 的 custom_verify 撞词致误判 FAILED）
            if any(marker in text for marker in _RISK_CONTROL_BODY_MARKERS):
                jar.cool_down()
                raise RiskControlError(f"HTTP {status}: {text[:200]}") from exc
            raise StructureDriftError(f"响应非 JSON（HTTP {status}）: {text[:200]}") from exc
        if not isinstance(data, dict):
            raise StructureDriftError(f"响应顶层不是对象（HTTP {status}）")
        return data

    async def _sign(self, path: str, params: str, jar: _CookieJar) -> str:
        """产出最终 query：signer 在线用页面 SDK 参数（原样追加），否则本地 a_bogus。"""
        if self._signer is None:
            return self._abogus.generate_abogus(params)[0]
        try:
            sdk_params = await self._signer.sign(path, params, self._user_agent, jar.cookie)
        except (SignerUnavailableError, SignerRejectedError) as exc:
            # 基础设施问题 ≠ 风控：不冷却 jar，回退本地签名（灰度期端点仍可用）
            logger.warning("social_douyin_signer_fallback", error=str(exc))
            return self._abogus.generate_abogus(params)[0]
        # SDK 参数原样追加，绝不补任何未签参数（msToken 事故：补参 = Sign Invalid）
        return f"{params}&{urlencode(sdk_params)}"

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
