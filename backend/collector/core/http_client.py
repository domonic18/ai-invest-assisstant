"""东财接口共享的限流 HTTP 客户端。

东财 WAF 按 TLS 指纹 + 路径拦截：requests/httpx 指纹访问 push2 clist 系
接口会被 TCP 层断连（RemoteDisconnected），须走 :func:`eastmoney_get_chrome`
（curl_cffi Chrome 指纹）。所有东财采集器必须经由本模块发起请求：
全局最小间隔 + 随机抖动降低触发限流的概率，连接级重试覆盖网关类瞬时
错误（429/5xx）。
"""

import random
import threading
import time
from typing import Any

import requests
from curl_cffi.requests import Response as CffiResponse
from curl_cffi.requests import Session as CffiSession
from curl_cffi.requests import exceptions as cffi_exceptions
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

EM_MIN_INTERVAL = 1.0  # 两次东财请求的最小间隔（秒）
_EM_JITTER_RANGE = (0.1, 0.5)
_CHROME_RETRY_ATTEMPTS = 3  # 连接级瞬时错误的尝试次数（含首次）
_CHROME_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    # push2 接口缺失 Referer 会直接断开连接
    "Referer": "https://data.eastmoney.com/bkzj/hy.html",
}


class _RateLimiter:
    """进程内全局限流器：保证相邻请求间隔不小于最小间隔（含抖动）。"""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            delay = self._min_interval + random.uniform(*_EM_JITTER_RANGE) - elapsed
            if delay > 0:
                time.sleep(delay)
            self._last_request_at = time.monotonic()


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(_DEFAULT_HEADERS)
    return session


_session = _build_session()
_limiter = _RateLimiter(EM_MIN_INTERVAL)


def eastmoney_get(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15,
) -> requests.Response:
    """限流 + 重试的东财 GET 请求，返回已校验状态码的响应。"""
    _limiter.wait()
    response = _session.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response


_cffi_session: CffiSession | None = None
_cffi_session_lock = threading.Lock()


def _get_cffi_session() -> CffiSession:
    global _cffi_session
    if _cffi_session is None:
        with _cffi_session_lock:
            if _cffi_session is None:
                session: CffiSession = CffiSession(impersonate="chrome")
                session.headers.update(_DEFAULT_HEADERS)
                _cffi_session = session
    return _cffi_session


def eastmoney_get_chrome(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15,
) -> CffiResponse:
    """Chrome TLS 指纹的东财 GET（含连接级重试）。

    push2 clist 系接口对 requests/httpx 指纹按 TLS 指纹断连，curl_cffi 的
    Chrome 指纹可正常访问；限流与 :func:`eastmoney_get` 共用。连接被
    切断（WAF 瞬时限流）与 429/5xx 视为瞬时错误重试，重试间由限流器
    自然退避。
    """
    last_error: Exception | None = None
    for _ in range(_CHROME_RETRY_ATTEMPTS):
        _limiter.wait()
        try:
            response: CffiResponse = _get_cffi_session().get(
                url, params=params, headers=headers, timeout=timeout
            )
            response.raise_for_status()
            return response
        except cffi_exceptions.HTTPError as exc:
            if exc.response.status_code not in _CHROME_RETRY_STATUSES:
                raise
            last_error = exc
        except (cffi_exceptions.ConnectionError, cffi_exceptions.Timeout) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error
