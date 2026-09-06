"""登录防爆破限流契约测试（redis 交互全 mock）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import login_throttle


@pytest.mark.unit
class TestLoginThrottle:
    @pytest.mark.asyncio
    async def test_not_locked_when_no_failures(self) -> None:
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        with patch("app.core.login_throttle.get_redis", return_value=redis):
            assert await login_throttle.locked_seconds("u", "ip") == 0

    @pytest.mark.asyncio
    async def test_not_locked_below_threshold(self) -> None:
        redis = MagicMock()
        redis.get = AsyncMock(return_value=b"4")
        with patch("app.core.login_throttle.get_redis", return_value=redis):
            assert await login_throttle.locked_seconds("u", "ip") == 0

    @pytest.mark.asyncio
    async def test_locked_at_threshold_returns_ttl(self) -> None:
        redis = MagicMock()
        redis.get = AsyncMock(return_value=b"5")
        redis.ttl = AsyncMock(return_value=300)
        with patch("app.core.login_throttle.get_redis", return_value=redis):
            assert await login_throttle.locked_seconds("u", "ip") == 300

    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self) -> None:
        redis = MagicMock()
        redis.get = AsyncMock(side_effect=RedisConnectionError("down"))
        with patch("app.core.login_throttle.get_redis", return_value=redis):
            assert await login_throttle.locked_seconds("u", "ip") == 0

    @pytest.mark.asyncio
    async def test_record_failure_incr_with_window(self) -> None:
        redis = MagicMock()
        pipe = MagicMock()
        pipe.incr = MagicMock()
        pipe.expire = MagicMock()
        pipe.execute = AsyncMock(return_value=[1, True])
        redis.pipeline = MagicMock(return_value=pipe)
        with patch("app.core.login_throttle.get_redis", return_value=redis):
            await login_throttle.record_failure("u", "ip")

        pipe.incr.assert_called_once_with("login:fail:u:ip")
        pipe.expire.assert_called_once_with(
            "login:fail:u:ip", login_throttle.LOCK_SECONDS, nx=True
        )

    @pytest.mark.asyncio
    async def test_record_failure_fail_open_on_redis_error(self) -> None:
        redis = MagicMock()
        redis.pipeline = MagicMock(side_effect=RedisConnectionError("down"))
        with patch("app.core.login_throttle.get_redis", return_value=redis):
            await login_throttle.record_failure("u", "ip")

    @pytest.mark.asyncio
    async def test_reset_deletes_counter(self) -> None:
        redis = MagicMock()
        redis.delete = AsyncMock()
        with patch("app.core.login_throttle.get_redis", return_value=redis):
            await login_throttle.reset_failures("u", "ip")

        redis.delete.assert_awaited_once_with("login:fail:u:ip")
