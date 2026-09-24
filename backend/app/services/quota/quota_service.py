"""配额闸门：PG 是账本、Redis 是闸门（arch/10 §4）。

- 剩余额镜像 ``quota:remain:{user_id}``：整数为剩余 tokens，哨兵 ``inf`` 为不限额；
- 预扣/结算用 Lua 单脚本保证原子（读-比-扣一次 EVAL）；
- 键 miss / 被失效时从 PG 重建（total − Σ系统出口用量；豁免用户写 ``inf``）；
- Redis 不可达时降级 PG 校验放行（容忍并发窗口，AI 可用性优先），不 fail-closed。

回调上下文无请求级 DB 会话，本服务自建短会话完成重建与降级查询。
"""

import structlog
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.database import AsyncSessionLocal
from app.core.exceptions import QuotaExhaustedError
from app.models.account_quota import UserAiQuota, UserTokenUsage
from app.models.user import User
from app.services.quota import account_settings
from app.services.quota.constants import (
    OUTLET_SYSTEM,
    QUOTA_REMAIN_KEY_TEMPLATE,
    QUOTA_REMAIN_TTL_SECONDS,
    QUOTA_UNLIMITED_SENTINEL,
)

logger = structlog.get_logger(__name__)

# 预扣拒绝（剩余不足）
RESERVE_DENIED = -1
# 键缺失需重建（内部信号，不对外）
_MISS = -2
# Redis 降级 PG 校验放行（未发生真实预扣，调用方不得对该值结算回补）
RESERVE_DEGRADED = -3
# 不限额哨兵返回值（与 Lua 脚本 inf 分支同值）
_UNLIMITED_PROBE = 9007199254740992

# 读-比-扣原子脚本：nil → -2；inf → 放行不扣；不足 → -1；命中 → DECRBY 并返回余量
_RESERVE_LUA = """
local val = redis.call('GET', KEYS[1])
if not val then return -2 end
if val == 'inf' then return 9007199254740992 end
local remain = tonumber(val)
local est = tonumber(ARGV[1])
if remain < est then return -1 end
redis.call('DECRBY', KEYS[1], est)
redis.call('EXPIRE', KEYS[1], ARGV[2])
return remain - est
"""

# 结算脚本：回补 reserved - actual 差额（actual 超预扣照扣，可为负余量）。
# 不刷新 TTL：键的存活期锚定最后一次 reserve，悬挂预扣最迟在 TTL 到期后
# 由 PG 重建吸收；settle 续期会让该自愈上限随活跃使用无限后移。
_SETTLE_LUA = """
local val = redis.call('GET', KEYS[1])
if (not val) or val == 'inf' then return 0 end
local diff = tonumber(ARGV[1]) - tonumber(ARGV[2])
if diff ~= 0 then redis.call('INCRBY', KEYS[1], diff) end
return 1
"""


def _key(user_id: int) -> str:
    return QUOTA_REMAIN_KEY_TEMPLATE.format(user_id=user_id)


async def _compute_from_pg(session: AsyncSession, user_id: int) -> int | None:
    """从 PG 重算剩余额；返回 None 表示不限额（豁免）。

    豁免口径：无配额行视作 0（未发额即不可用系统模型）；total NULL 不限；
    admin 角色在豁免开关开启时不限（仍计量）。
    """
    quota = await session.get(UserAiQuota, user_id)
    user = await session.get(User, user_id)
    if user is None:
        return 0
    if quota is None:
        return 0
    if quota.total_tokens is None:
        return None
    if user.role == "admin" and await account_settings.get_admin_exempt(session):
        return None
    used = (
        await session.execute(
            select(func.coalesce(func.sum(UserTokenUsage.total_tokens), 0)).where(
                UserTokenUsage.user_id == user_id,
                UserTokenUsage.outlet == OUTLET_SYSTEM,
            )
        )
    ).scalar_one()
    return int(quota.total_tokens) - int(used)


async def precheck(user_id: int) -> None:
    """入口显式预检：剩余 ≤ 0 直接抛 QuotaExhaustedError（不扣减）。

    LangChain callback manager 会捕获并吞掉 callback 内抛出的异常（仅打印
    "Error in ... callback"），模型调用照常执行——配额拦截**不能**依赖 callback
    异常传播，必须在 AI 入口（路由层）显式调用本函数，REST 路径经全局
    handler 转 429。
    """
    remaining = await check_and_reserve(user_id, 0)
    if remaining != RESERVE_DEGRADED and remaining <= 0:
        raise QuotaExhaustedError()


async def rebuild(user_id: int) -> int | None:
    """从 PG 重建 Redis 剩余额镜像（自建短会话）。"""
    async with AsyncSessionLocal() as session:
        remaining = await _compute_from_pg(session, user_id)
    value = QUOTA_UNLIMITED_SENTINEL if remaining is None else str(remaining)
    try:
        await get_redis().set(_key(user_id), value, ex=QUOTA_REMAIN_TTL_SECONDS)
    except RedisError as exc:
        logger.warning("quota_rebuild_redis_unavailable", user_id=user_id, error=str(exc))
    return remaining


async def check_and_reserve(user_id: int, estimate: int) -> int:
    """预扣配额；返回预扣后余量（RESERVE_DENIED=不足）。

    键缺失时重建一次后重试；Redis 不可达时降级 PG 校验：剩余为正返回
    RESERVE_DEGRADED 放行（跳过预扣，容忍并发窗口，调用方不得结算），
    不限额返回不限额哨兵。
    """
    try:
        redis = get_redis()
        result = int(
            await redis.eval(
                _RESERVE_LUA, 1, _key(user_id), estimate, QUOTA_REMAIN_TTL_SECONDS
            )
        )
        if result == _MISS:
            await rebuild(user_id)
            result = int(
                await redis.eval(
                    _RESERVE_LUA, 1, _key(user_id), estimate, QUOTA_REMAIN_TTL_SECONDS
                )
            )
        return result
    except RedisError as exc:
        logger.warning("quota_gate_redis_degraded_pg_check", user_id=user_id, error=str(exc))
        async with AsyncSessionLocal() as session:
            remaining = await _compute_from_pg(session, user_id)
        if remaining is None:
            # 不限额：降级期间补写镜像，恢复后免重建
            try:
                await get_redis().set(
                    _key(user_id), QUOTA_UNLIMITED_SENTINEL, ex=QUOTA_REMAIN_TTL_SECONDS
                )
            except RedisError:
                pass
            return _UNLIMITED_PROBE
        if remaining > 0:
            return RESERVE_DEGRADED
        return RESERVE_DENIED


async def settle(user_id: int, reserved: int, actual: int) -> None:
    """按实际用量结算：回补 reserved − actual 差额（失败仅记日志，不影响主请求）。"""
    if reserved == actual:
        return
    try:
        await get_redis().eval(_SETTLE_LUA, 1, _key(user_id), reserved, actual)
    except RedisError as exc:
        logger.warning("quota_settle_failed", user_id=user_id, error=str(exc))


async def invalidate(user_id: int) -> None:
    """配额调整/审批发额后失效镜像，下一次调用从 PG 重建。"""
    try:
        await get_redis().delete(_key(user_id))
    except RedisError as exc:
        logger.warning("quota_invalidate_failed", user_id=user_id, error=str(exc))


async def invalidate_all() -> None:
    """全局设置变更（如 admin 豁免开关）后失效全部镜像（SCAN 遍历，键空间小）。"""
    pattern = QUOTA_REMAIN_KEY_TEMPLATE.format(user_id="*")
    try:
        redis = get_redis()
        async for key in redis.scan_iter(match=pattern, count=100):
            await redis.delete(key)
    except RedisError as exc:
        logger.warning("quota_invalidate_all_failed", error=str(exc))
