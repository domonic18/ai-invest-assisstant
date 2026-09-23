"""redis_lock 契约单测（mock redis client，不连真实 Redis）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import LockNotOwnedError

from app.core.locking import redis_lock


def _patch_client(release: AsyncMock) -> tuple[MagicMock, MagicMock]:
    client = MagicMock()
    lock = MagicMock()
    lock.acquire = AsyncMock(return_value=True)
    lock.release = release
    client.lock = MagicMock(return_value=lock)
    return client, lock


@pytest.mark.unit
class TestRedisLock:
    @pytest.mark.asyncio
    async def test_release_error_propagates_for_other_causes(self) -> None:
        release = AsyncMock(side_effect=RuntimeError("boom"))
        client, _ = _patch_client(release)
        with (
            patch("app.core.locking.get_redis", return_value=client),
            pytest.raises(RuntimeError, match="boom"),
        ):
            async with redis_lock("k"):
                pass

    @pytest.mark.asyncio
    async def test_expired_lock_release_is_swallowed(self) -> None:
        """持锁期间 TTL 过期：释放抛 LockNotOwnedError 应被吞掉，不向外传播。"""
        release = AsyncMock(side_effect=LockNotOwnedError("no longer owned"))
        client, lock = _patch_client(release)
        with patch("app.core.locking.get_redis", return_value=client):
            async with redis_lock("k", ttl=1) as acquired:
                assert acquired is True

        release.assert_awaited_once()
        lock.acquire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_acquired_skips_release(self) -> None:
        release = AsyncMock()
        client, lock = _patch_client(release)
        lock.acquire = AsyncMock(return_value=False)
        with patch("app.core.locking.get_redis", return_value=client):
            async with redis_lock("k", blocking=False) as acquired:
                assert acquired is False

        release.assert_not_awaited()
