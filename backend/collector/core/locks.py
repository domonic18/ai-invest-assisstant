"""Redis distributed lock for collector/AI tasks."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis

from collector.core.config import redis_url


@asynccontextmanager
async def redis_lock(
    key: str,
    ttl: int = 300,
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
    client = aioredis.from_url(redis_url, decode_responses=True)
    lock = client.lock(f"lock:{key}", timeout=ttl, thread_local=False)
    acquired = await lock.acquire(blocking=blocking, blocking_timeout=blocking_timeout)
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()
        await client.aclose()
