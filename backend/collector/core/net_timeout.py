"""为进程内所有 ``requests`` 调用注入默认超时的兜底补丁。

第三方采集库（akshare 等）内部大量使用 ``requests`` 且不传 timeout——
requests 官方文档明确默认无超时，连接一旦被对端黑洞（如 CDN 静默丢包）
线程将永久阻塞（2026-09-23 生产挂死事故根因三）。本模块在 worker 子进程
启动时把 ``Session.request`` 包装一层 ``kwargs.setdefault("timeout", ...)``：
未显式传 timeout 的调用获得兜底值，显式传值的不受影响。

只 patch requests 而非 ``socket.setdefaulttimeout``：后者会波及同进程内
asyncpg/redis/minio 的裸 socket（长查询单次 recv 等待可能被误杀），爆破
半径最小原则下只影响「没传 timeout 的 requests 调用」这一明确病灶。
"""

from typing import Any

import requests
import structlog

logger = structlog.get_logger(__name__)

_original_request: Any = None


def patch_requests_default_timeout(seconds: float) -> None:
    """给 ``requests.Session.request`` 注入默认 timeout（幂等）。

    Args:
        seconds: 未显式传 timeout 时的兜底超时（秒）。
    """
    global _original_request  # noqa: PLW0603

    if _original_request is None:
        _original_request = requests.Session.request

    def _request_with_default_timeout(session: requests.Session, *args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", seconds)
        return _original_request(session, *args, **kwargs)

    requests.Session.request = _request_with_default_timeout  # type: ignore[method-assign,assignment]
    logger.info("requests_default_timeout_patched", seconds=seconds)
