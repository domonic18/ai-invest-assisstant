"""登录防爆破：redis 失败计数限流（fail-open）。

按「用户名 + 来源 IP」计数，连续失败达阈值后锁定一个固定窗口；
成功登录即清零。redis 不可用时放行（fail-open）——限流基础设施故障
不应把登录整体打挂，审计日志仍会记录每次失败。
"""

import structlog
from redis.exceptions import RedisError

from app.core.cache import get_redis

logger = structlog.get_logger(__name__)

MAX_FAILURES = 5
LOCK_SECONDS = 900


def _key(username: str, client_ip: str) -> str:
    return f"login:fail:{username}:{client_ip}"


async def locked_seconds(username: str, client_ip: str) -> int:
    """该 (用户名, IP) 组合剩余锁定秒数；未锁定返回 0。"""
    key = _key(username, client_ip)
    try:
        redis = get_redis()
        count = await redis.get(key)
        if count is None or int(count) < MAX_FAILURES:
            return 0
        return max(await redis.ttl(key), 0)
    except RedisError:
        logger.warning("login_throttle_unavailable")
        return 0


async def record_failure(username: str, client_ip: str) -> None:
    """记录一次登录失败（首次失败起算固定窗口）。"""
    key = _key(username, client_ip)
    try:
        redis = get_redis()
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, LOCK_SECONDS, nx=True)
        await pipe.execute()
    except RedisError:
        logger.warning("login_throttle_unavailable")


async def reset_failures(username: str, client_ip: str) -> None:
    """登录成功后清除失败计数。"""
    try:
        await get_redis().delete(_key(username, client_ip))
    except RedisError:
        logger.warning("login_throttle_unavailable")
