"""Redis 分布式锁：跨 service / agent / collector 共享。

收编自 ``collector/core/locks.py``——该模块在 collector 内部零调用，仅给 app 用，
违反 app → collector 单向依赖。迁到 ``app/core`` 后复用 ``app.core.cache.get_redis``
共享连接池，避免每次加锁新建 client。
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from redis.exceptions import LockNotOwnedError

from app.core.cache import get_redis

logger = structlog.get_logger(__name__)

DEFAULT_LOCK_TTL_SECONDS = 300
# LLM 生成类任务（复盘归因/个股分析）实际耗时可达 10 分钟以上，
# 锁 TTL 必须覆盖最坏运行时长，否则互斥保护中途失效、并发实例可重复生成。
GENERATION_LOCK_TTL_SECONDS = 1800


@asynccontextmanager
async def redis_lock(
    key: str,
    ttl: int = DEFAULT_LOCK_TTL_SECONDS,
    blocking: bool = True,
    blocking_timeout: float = 30,
) -> AsyncGenerator[bool, None]:
    """获取 Redis 分布式锁。

    Args:
        key: 锁标识（不含 ``lock:`` 前缀）。
        ttl: 锁自动释放时间（秒）。
        blocking: 是否阻塞等待锁；False 时立即返回是否获取成功。
        blocking_timeout: 阻塞等待的最长时间（秒）。

    Yields:
        是否成功获取到锁。
    """
    client = get_redis()
    lock = client.lock(f"lock:{key}", timeout=ttl, thread_local=False)
    acquired = await lock.acquire(blocking=blocking, blocking_timeout=blocking_timeout)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                await lock.release()
            except LockNotOwnedError:
                # 持锁期间 TTL 过期（如 LLM 生成超过 ttl）：锁的互斥目的已随过期失效，
                # 释放失败是良性事件，吞掉以免把成功的生成误判为任务失败。
                logger.warning("redis_lock_expired_before_release", key=key)
