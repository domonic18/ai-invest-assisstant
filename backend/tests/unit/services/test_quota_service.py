"""配额闸门单测：Redis Lua 预扣/结算语义 + PG 重算口径（不触真实 Redis/PG）。"""

from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.account_quota import SystemSetting, UserAiQuota, UserTokenUsage
from app.models.user import User
from app.services.quota import quota_service
from app.services.quota.constants import OUTLET_SYSTEM
from app.services.quota.quota_service import RESERVE_DENIED

pytestmark = pytest.mark.unit


class FakeRedis:
    """按 quota_service 两条 Lua 脚本的语义模拟 EVAL（整数/inf 哨兵）。"""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def eval(self, script: str, numkeys: int, key: str, *args: object) -> int:
        if "DECRBY" in script:  # _RESERVE_LUA: estimate, ttl
            val = self.store.get(key)
            if val is None:
                return -2
            if val == "inf":
                return 9007199254740992
            remain, estimate = int(val), int(str(args[0]))
            if remain < estimate:
                return -1
            self.store[key] = str(remain - estimate)
            return remain - estimate
        # _SETTLE_LUA: reserved, actual（无 EXPIRE，键 TTL 锚定 reserve）
        val = self.store.get(key)
        if val is None or val == "inf":
            return 0
        diff = int(str(args[0])) - int(str(args[1]))
        self.store[key] = str(int(val) + diff)
        return 1

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    redis = FakeRedis()
    monkeypatch.setattr(quota_service, "get_redis", lambda: redis)
    return redis


async def test_reserve_hit_deducts(fake_redis: FakeRedis) -> None:
    fake_redis.store["quota:remain:1"] = "100"
    remaining = await quota_service.check_and_reserve(1, 30)
    assert remaining == 70
    assert fake_redis.store["quota:remain:1"] == "70"


async def test_reserve_insufficient_denied(fake_redis: FakeRedis) -> None:
    fake_redis.store["quota:remain:1"] = "10"
    assert await quota_service.check_and_reserve(1, 30) == RESERVE_DENIED
    assert fake_redis.store["quota:remain:1"] == "10"


async def test_reserve_unlimited_never_deducts(fake_redis: FakeRedis) -> None:
    fake_redis.store["quota:remain:9"] = "inf"
    for _ in range(3):
        assert await quota_service.check_and_reserve(9, 10**6) > 0
    assert fake_redis.store["quota:remain:9"] == "inf"


async def test_miss_rebuilds_once_then_reserves(fake_redis: FakeRedis) -> None:
    async def fake_rebuild(user_id: int) -> int | None:
        fake_redis.store["quota:remain:5"] = "50"
        return 50

    with patch.object(quota_service, "rebuild", side_effect=fake_rebuild):
        assert await quota_service.check_and_reserve(5, 20) == 30


async def test_settle_refunds_difference(fake_redis: FakeRedis) -> None:
    fake_redis.store["quota:remain:1"] = "70"  # 预扣 30 后
    await quota_service.settle(1, 30, 15)
    assert fake_redis.store["quota:remain:1"] == "85"


async def test_settle_overdraft_stays_negative(fake_redis: FakeRedis) -> None:
    fake_redis.store["quota:remain:1"] = "5"
    await quota_service.settle(1, 30, 60)
    assert fake_redis.store["quota:remain:1"] == "-25"


async def test_precheck_blocks_zero_and_negative(fake_redis: FakeRedis) -> None:
    from app.core.exceptions import QuotaExhaustedError

    fake_redis.store["quota:remain:1"] = "0"
    with pytest.raises(QuotaExhaustedError):
        await quota_service.precheck(1)

    fake_redis.store["quota:remain:1"] = "-25"
    with pytest.raises(QuotaExhaustedError):
        await quota_service.precheck(1)


async def test_precheck_allows_positive_and_unlimited(fake_redis: FakeRedis) -> None:
    fake_redis.store["quota:remain:1"] = "10"
    await quota_service.precheck(1)  # 不抛
    assert fake_redis.store["quota:remain:1"] == "10"  # 预检不扣减

    fake_redis.store["quota:remain:1"] = "inf"
    await quota_service.precheck(1)


async def test_invalidate_deletes_key(fake_redis: FakeRedis) -> None:
    fake_redis.store["quota:remain:1"] = "70"
    await quota_service.invalidate(1)
    assert "quota:remain:1" not in fake_redis.store


# ---- PG 重算口径（sqlite） ----


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[User.__table__, UserAiQuota.__table__, UserTokenUsage.__table__, SystemSetting.__table__],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _add_user(session: AsyncSession, **kwargs: object) -> User:
    user = User(
        username=kwargs.pop("username", "u"),
        email=kwargs.pop("email", "u@x.com"),
        password_hash="x",
        role=kwargs.pop("role", "user"),
    )
    for key, value in kwargs.items():
        setattr(user, key, value)
    session.add(user)
    await session.flush()
    return user


async def test_compute_no_quota_row_means_zero(session: AsyncSession) -> None:
    user = await _add_user(session)
    assert await quota_service._compute_from_pg(session, user.id) == 0


async def test_compute_total_null_is_unlimited(session: AsyncSession) -> None:
    user = await _add_user(session)
    session.add(UserAiQuota(user_id=user.id, total_tokens=None))
    await session.flush()
    assert await quota_service._compute_from_pg(session, user.id) is None


async def test_compute_subtracts_system_outlet_only(session: AsyncSession) -> None:
    user = await _add_user(session)
    session.add(UserAiQuota(user_id=user.id, total_tokens=1000))
    session.add(UserTokenUsage(user_id=user.id, feature="assistant", model_name="m", provider="p", outlet=OUTLET_SYSTEM, prompt_tokens=100, completion_tokens=100, total_tokens=200, estimated=False))
    session.add(UserTokenUsage(user_id=user.id, feature="assistant", model_name="m", provider="byok", outlet="byok", prompt_tokens=50, completion_tokens=50, total_tokens=100, estimated=False))
    await session.flush()
    # BYOK 消耗不占配额
    assert await quota_service._compute_from_pg(session, user.id) == 800


async def test_compute_admin_exempt_is_unlimited(session: AsyncSession) -> None:
    user = await _add_user(session, role="admin")
    session.add(UserAiQuota(user_id=user.id, total_tokens=100))
    session.add(SystemSetting(key="quota.admin_exempt", value=True))
    await session.flush()
    assert await quota_service._compute_from_pg(session, user.id) is None


async def test_redis_down_degrades_to_pg_check(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    user = await _add_user(session)
    session.add(UserAiQuota(user_id=user.id, total_tokens=100))

    monkeypatch.setattr(quota_service, "get_redis", lambda: _RaisingProxy())
    monkeypatch.setattr(quota_service, "AsyncSessionLocal", lambda: _SessionCtx(session))

    assert await quota_service.check_and_reserve(user.id, 50) == quota_service.RESERVE_DEGRADED

    session.add(UserTokenUsage(user_id=user.id, feature="page", model_name="m", provider="p", outlet=OUTLET_SYSTEM, prompt_tokens=80, completion_tokens=80, total_tokens=160, estimated=False))
    await session.flush()
    assert await quota_service.check_and_reserve(user.id, 50) == RESERVE_DENIED


async def test_precheck_degraded_sentinel_passes() -> None:
    """降级放行哨兵（负值）不得触发 QuotaExhaustedError。"""
    sentinel = AsyncMock(return_value=quota_service.RESERVE_DEGRADED)
    with patch.object(quota_service, "check_and_reserve", sentinel):
        await quota_service.precheck(1)  # 不抛
        sentinel.assert_awaited_once_with(1, 0)


async def test_redis_down_unlimited_degrades_with_probe(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    user = await _add_user(session)
    session.add(UserAiQuota(user_id=user.id, total_tokens=None))
    monkeypatch.setattr(quota_service, "get_redis", lambda: _RaisingProxy())
    monkeypatch.setattr(quota_service, "AsyncSessionLocal", lambda: _SessionCtx(session))

    assert await quota_service.check_and_reserve(user.id, 50) == quota_service._UNLIMITED_PROBE


class _RaisingProxy:
    def __getattr__(self, name: str) -> object:
        async def _raise(*args: object, **kwargs: object) -> object:
            raise RedisError("down")

        return _raise


class _SessionCtx:
    """把降级路径的 AsyncSessionLocal 替换为测试 sqlite 会话。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: object) -> bool:
        return False
