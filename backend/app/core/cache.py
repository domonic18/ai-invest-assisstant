"""进程级共享 Redis 客户端。

收编各 service 中重复的 ``_redis()`` 单例逻辑（连接池复用，避免每次读写都新建连接）。
"""

from typing import Any

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis_client: Redis | None = None


def get_redis() -> Redis:
    """返回进程级共享 Redis 客户端（懒初始化）。"""
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(str(get_settings().redis_url))
    return _redis_client


def _redis() -> Any:
    """向后兼容旧调用点；新代码请直接使用 ``get_redis()``。"""
    return get_redis()
