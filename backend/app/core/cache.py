"""进程级共享 Redis 客户端与容错读写助手。

收编各 service 中重复的 ``_redis()`` 单例逻辑（连接池复用，避免每次读写都新建连接）。

容错约定：对 web-api 而言 Redis 是加速/实时增强层，不可达时 ``cache_*`` 助手
记限频告警并返回中性值，调用方走 DB 降级路径；缓存基础设施故障不允许把
接口打挂（与 login_throttle 的 fail-open 同一原则）。
"""

import time

import structlog
from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_redis_client: Redis | None = None
_last_warn_at = 0.0
_WARN_INTERVAL_SECONDS = 60.0


def get_redis() -> Redis:
    """返回进程级共享 Redis 客户端（懒初始化，带快速失败超时）。"""
    global _redis_client
    if _redis_client is None:
        timeout = get_settings().redis_socket_timeout
        _redis_client = from_url(
            str(get_settings().redis_url),
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
    return _redis_client


def _warn_throttled(operation: str, exc: Exception) -> None:
    """Redis 不可用时告警限频（网络隔离时每请求都失败，避免日志刷屏）。"""
    global _last_warn_at
    now = time.monotonic()
    if now - _last_warn_at >= _WARN_INTERVAL_SECONDS:
        _last_warn_at = now
        logger.warning("cache_unavailable", operation=operation, error=str(exc))


async def cache_get(key: str) -> str | bytes | None:
    """容错 GET；Redis 不可达返回 None。"""
    try:
        return await get_redis().get(key)
    except RedisError as exc:
        _warn_throttled("get", exc)
        return None


async def cache_mget(*keys: str) -> list[str | bytes | None]:
    """容错批量 GET；Redis 不可达返回与键数等长的 None 列表。"""
    try:
        return list(await get_redis().mget(*keys))
    except RedisError as exc:
        _warn_throttled("mget", exc)
        return [None] * len(keys)


async def cache_exists(key: str) -> bool:
    """容错 EXISTS；Redis 不可达返回 False。"""
    try:
        return bool(await get_redis().exists(key))
    except RedisError as exc:
        _warn_throttled("exists", exc)
        return False


async def cache_set(key: str, value: str, *, ex: int | None = None) -> bool:
    """容错 SET；写失败只损失缓存命中，不影响主流程。"""
    try:
        await get_redis().set(key, value, ex=ex)
        return True
    except RedisError as exc:
        _warn_throttled("set", exc)
        return False
