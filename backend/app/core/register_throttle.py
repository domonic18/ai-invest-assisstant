"""注册接口 IP 限流：Redis 每日计数（fail-open）。

防公网滥用注册申请（默认 5 次/IP/天，``AUTH_REGISTER_IP_LIMIT`` 可配）。
redis 不可用时放行（fail-open）——与 login_throttle 同一原则，
限流基础设施故障不应把注册整体打挂。
"""

import structlog
from redis.exceptions import RedisError

from app.core.cache import get_redis
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_WINDOW_SECONDS = 86400


def _key(client_ip: str) -> str:
    return f"auth:register:ip:{client_ip}"


async def check_ip_allowed(client_ip: str) -> bool:
    """该 IP 今日注册提交次数是否未达上限。"""
    limit = get_settings().auth_register_ip_limit
    if limit <= 0:
        return True
    try:
        count = await get_redis().get(_key(client_ip))
        return count is None or int(count) < limit
    except RedisError:
        logger.warning("register_throttle_unavailable")
        return True


async def record_submission(client_ip: str) -> None:
    """记录一次注册提交（首次起算 24h 窗口）。"""
    try:
        redis = get_redis()
        pipe = redis.pipeline()
        pipe.incr(_key(client_ip))
        pipe.expire(_key(client_ip), _WINDOW_SECONDS, nx=True)
        await pipe.execute()
    except RedisError:
        logger.warning("register_throttle_unavailable")
