"""Shared rate-limited HTTP client for EastMoney endpoints.

东财 push2 系列接口对高频请求会做 IP 级临时封禁（RemoteDisconnected），
所有东财采集器必须经由本模块发起请求：全局最小间隔 + 随机抖动降低触发
限流的概率，连接级重试覆盖网关类瞬时错误（429/5xx）。
"""

import random
import threading
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

EM_MIN_INTERVAL = 1.0  # 两次东财请求的最小间隔（秒）
_EM_JITTER_RANGE = (0.1, 0.5)

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
