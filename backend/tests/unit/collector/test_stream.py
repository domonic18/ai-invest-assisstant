"""cls 电报驻留 stream 单测：游标自举、增量过滤、看门狗补漏、退避、优雅停止。"""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.runtime import stream as stream_mod
from collector.runtime.stream import (
    BACKFILL_MAX_PAGES,
    BACKOFF_INITIAL,
    BACKOFF_MAX,
    CURSOR_KEY,
    HEARTBEAT_KEY,
    HEARTBEAT_TTL,
    ClsTelegraphStream,
)


class FakeRedis:
    """只覆盖 stream 用到的 get/set/aclose 的最小 Redis 假件。"""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        self.ttls[key] = ex

    async def aclose(self) -> None:
        pass


def _row(msg_id: int, ts: int) -> dict:
    return {
        "cls_msg_id": msg_id,
        "publish_time": datetime.fromtimestamp(ts, tz=timezone.utc),
    }


def _make_stream(
    store: AsyncMock | None = None, cursor: int | None = None, **kwargs
) -> tuple[ClsTelegraphStream, AsyncMock, FakeRedis]:
    store = store or AsyncMock(return_value=2)
    collector = MagicMock()
    collector.store = store
    fake = FakeRedis()
    s = ClsTelegraphStream(collector, fake, **kwargs)
    if cursor is not None:
        s._cursor = cursor
    return s, store, fake


@pytest.mark.unit
class TestLoadCursor:
    async def test_prefers_redis(self) -> None:
        s, _, fake = _make_stream()
        fake.data[CURSOR_KEY] = "1785696000"
        bootstrap = AsyncMock()
        with patch.object(stream_mod, "db_max_publish_time", bootstrap):
            assert await s.load_cursor() == 1785696000
        bootstrap.assert_not_awaited()

    async def test_bootstraps_from_db(self) -> None:
        s, _, fake = _make_stream()
        with patch.object(
            stream_mod, "db_max_publish_time", AsyncMock(return_value=1785696000)
        ):
            assert await s.load_cursor() == 1785696000
        assert fake.data[CURSOR_KEY] == "1785696000"

    async def test_empty_db_returns_zero(self) -> None:
        s, _, fake = _make_stream()
        with patch.object(stream_mod, "db_max_publish_time", AsyncMock(return_value=0)):
            assert await s.load_cursor() == 0
        assert CURSOR_KEY not in fake.data


@pytest.mark.unit
class TestPollOnce:
    async def test_stores_fresh_and_advances_cursor(self) -> None:
        now = int(time.time())
        s, store, fake = _make_stream(cursor=now - 60)
        with patch.object(
            stream_mod,
            "fetch_page",
            lambda last_time, rn: [_row(2, now + 30), _row(1, now + 10)],
        ):
            stored = await s.poll_once()

        assert stored == 2
        store.assert_awaited_once()
        assert [row["cls_msg_id"] for row in store.await_args.args[0]] == [2, 1]
        assert s._cursor == now + 30
        assert fake.data[CURSOR_KEY] == str(now + 30)
        assert fake.ttls[CURSOR_KEY] is None
        # 心跳带 TTL，供 healthcheck 判活
        assert int(fake.data[HEARTBEAT_KEY]) >= now
        assert fake.ttls[HEARTBEAT_KEY] == HEARTBEAT_TTL

    async def test_skips_stale_rows(self) -> None:
        now = int(time.time())
        s, store, fake = _make_stream(cursor=now)
        with patch.object(
            stream_mod,
            "fetch_page",
            lambda last_time, rn: [_row(1, now - 5), _row(0, now)],
        ):
            stored = await s.poll_once()

        assert stored == 0
        store.assert_not_awaited()
        assert s._cursor == now
        assert CURSOR_KEY not in fake.data

    async def test_backfill_walks_pages_when_lagging(self) -> None:
        now = int(time.time())
        floor = now - 400  # 滞后 > WATCHDOG_LAG，触发看门狗
        s, store, _ = _make_stream(cursor=floor)
        pages = {
            0: [_row(101, now), _row(100, now - 50)],
            now - 50: [_row(99, now - 100), _row(98, now - 350)],
            now - 350: [_row(97, now - 500)],
        }
        calls: list[int] = []

        def fetch(last_time: int, rn: int) -> list[dict]:
            calls.append(last_time)
            return pages[last_time]

        with patch.object(stream_mod, "fetch_page", fetch):
            stored = await s.poll_once()

        # 页 1 全新 2 条入库；补漏走页 2（2 条落入断连区间）；
        # 页 3 最旧一条已越过 floor 即停，不重复入库；游标仍为最新一页最大时间戳
        assert stored == 4
        assert calls == [0, now - 50, now - 350]
        assert store.await_count == 2
        assert [row["cls_msg_id"] for row in store.await_args_list[1].args[0]] == [99, 98]
        assert s._cursor == now

    async def test_backfill_page_cap(self) -> None:
        now = int(time.time())
        floor = now - 400
        s, _, _ = _make_stream(cursor=floor)
        calls: list[int] = []

        def fetch(last_time: int, rn: int) -> list[dict]:
            calls.append(last_time)
            if last_time == 0:
                return [_row(now - i, now - i) for i in range(20)]
            return [_row(last_time - 1 - k, last_time - 1 - k) for k in range(20)]

        with patch.object(stream_mod, "fetch_page", fetch):
            await s.poll_once()

        assert len(calls) == 1 + BACKFILL_MAX_PAGES


@pytest.mark.unit
class TestRunLoop:
    async def test_failure_backoff_then_recovery(self) -> None:
        now = int(time.time())
        s, store, fake = _make_stream(poll_interval=0.01)
        fake.data[CURSOR_KEY] = str(now - 5)
        state = {"calls": 0}
        warm = MagicMock()
        reset = MagicMock()

        def fetch(last_time: int, rn: int) -> list[dict]:
            state["calls"] += 1
            if state["calls"] == 1:
                raise RuntimeError("cls roll_list errno=403")
            s.request_stop()
            return []

        delays: list[float] = []

        async def fake_wait(delay: float) -> None:
            delays.append(delay)

        s._wait = fake_wait  # type: ignore[method-assign]
        with (
            patch.object(stream_mod, "fetch_page", fetch),
            patch.object(stream_mod, "warm_session", warm),
            patch.object(stream_mod, "reset_session", reset),
        ):
            await s.run()

        # 首次失败退避 BACKOFF_INITIAL 并重预热；成功后退避复位、恢复正常间隔
        assert delays == [BACKOFF_INITIAL, 0.01]
        assert state["calls"] == 2
        reset.assert_called_once()
        assert warm.call_count == 2  # 启动预热 + 失败后重预热
        assert s._backoff == BACKOFF_INITIAL
        store.assert_not_awaited()
        assert int(fake.data[HEARTBEAT_KEY]) >= now

    async def test_backoff_doubles_and_caps(self) -> None:
        s, _, fake = _make_stream()
        fake.data[CURSOR_KEY] = str(int(time.time()))
        state = {"calls": 0}

        def fetch(last_time: int, rn: int) -> list[dict]:
            state["calls"] += 1
            if state["calls"] >= 7:
                s.request_stop()
            raise RuntimeError("down")

        delays: list[float] = []

        async def fake_wait(delay: float) -> None:
            delays.append(delay)

        s._wait = fake_wait  # type: ignore[method-assign]
        with (
            patch.object(stream_mod, "fetch_page", fetch),
            patch.object(stream_mod, "warm_session", MagicMock()),
            patch.object(stream_mod, "reset_session", MagicMock()),
        ):
            await s.run()

        assert delays == [10.0, 20.0, 40.0, 80.0, 160.0, 320.0, BACKOFF_MAX]

    async def test_stop_event_interrupts_wait(self) -> None:
        s, _, _ = _make_stream()
        task = asyncio.create_task(s._wait(30))
        await asyncio.sleep(0.01)
        s.request_stop()
        await asyncio.wait_for(task, timeout=1)
