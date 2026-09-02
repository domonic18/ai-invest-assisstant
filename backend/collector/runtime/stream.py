"""财联社电报驻留采集进程（``python -m collector.runtime.stream``）。

与 Celery worker 并行的独立长驻进程：10s 轮询电报最新页增量写
``news_telegraph``（``cls_msg_id`` DO NOTHING 幂等）。游标与心跳存 Redis：

- ``collector:stream:cls_telegraph:last_time``：增量游标（Unix 秒，不设 TTL），
  缺失时以 DB ``max(publish_time)`` 自举；
- ``collector:stream:cls_telegraph:heartbeat``：心跳（TTL 120s），供容器
  healthcheck 判活——连续失败超过心跳 TTL 意味着数据源不可用，应重启重预热。

失败指数退避 10→600s 并重预热会话（丢弃被 WAF 拦截的 Cookie）。游标滞后超
5min（断连/WAF 长时间失败）时，下一轮成功拉取后从最新页向旧走页补漏——最新
一页可能已滚过断连期间的电报；补漏过滤以轮询前游标为界，页数封顶防失控，
重复写入由 DO NOTHING 兜底。SIGINT/SIGTERM 优雅退出。
"""

import asyncio
import signal
import time
from typing import Any

import redis.asyncio as redis_async
import structlog
from sqlalchemy import text

from collector.core.async_helpers import run_in_thread
from collector.core.logging import configure_logging
from collector.spiders.cls_telegraph import (
    ClsTelegraphCollector,
    fetch_page,
    reset_session,
    warm_session,
)

logger = structlog.get_logger(__name__)

CURSOR_KEY = "collector:stream:cls_telegraph:last_time"
HEARTBEAT_KEY = "collector:stream:cls_telegraph:heartbeat"
HEARTBEAT_TTL = 120
POLL_INTERVAL = 10.0
BACKOFF_INITIAL = 10.0
BACKOFF_MAX = 600.0
WATCHDOG_LAG = 300.0
BACKFILL_MAX_PAGES = 10
RN_PER_PAGE = 20


def _ts(row: dict[str, Any]) -> int:
    return int(row["publish_time"].timestamp())


async def db_max_publish_time() -> int:
    """news_telegraph 当前最大 publish_time（Unix 秒），空表返回 0。"""
    from collector.core.base import get_engine

    async with get_engine().connect() as conn:
        value = await conn.scalar(text("SELECT max(publish_time) FROM news_telegraph"))
    return int(value.timestamp()) if value is not None else 0


class ClsTelegraphStream:
    """cls 电报轮询循环：增量拉取 + 看门狗补漏 + 心跳 + 指数退避。"""

    def __init__(
        self,
        collector: ClsTelegraphCollector,
        redis_client: Any,
        *,
        poll_interval: float = POLL_INTERVAL,
    ) -> None:
        self._collector = collector
        self._redis = redis_client
        self.poll_interval = poll_interval
        self._cursor = 0
        self._backoff = BACKOFF_INITIAL
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        """请求停止（信号处理器调用，协作式退出）。"""
        self._stop.set()

    async def load_cursor(self) -> int:
        """读 Redis 游标；缺失时以 DB max(publish_time) 自举并回写。"""
        raw = await self._redis.get(CURSOR_KEY)
        if raw:
            return int(raw)
        cursor = await db_max_publish_time()
        if cursor:
            await self._redis.set(CURSOR_KEY, str(cursor))
        return cursor

    async def poll_once(self) -> int:
        """轮询一次，返回新入库条数。

        增量取最新一页；轮询前游标已滞后超 WATCHDOG_LAG（断连恢复）时，
        从最新页最旧一条向旧走页补漏，覆盖最新页已滚过的区间。
        """
        floor = self._cursor
        needs_backfill = time.time() - floor > WATCHDOG_LAG
        rows = await self._fetch_page(0)
        stored = await self._store_fresh(rows, floor)
        if stored:
            await self._advance_cursor(rows)
        if needs_backfill and rows:
            stored += await self._backfill(floor, min(_ts(row) for row in rows))
        await self._heartbeat()
        return stored

    async def _fetch_page(self, last_time: int) -> list[dict[str, Any]]:
        return await run_in_thread(fetch_page, last_time, RN_PER_PAGE)

    async def _store_fresh(
        self, rows: list[dict[str, Any]], floor: int
    ) -> int:
        """入库 publish_time 晚于 floor 的行，返回条数。"""
        fresh = [row for row in rows if _ts(row) > floor]
        if not fresh:
            return 0
        await self._collector.store(fresh)
        return len(fresh)

    async def _advance_cursor(self, rows: list[dict[str, Any]]) -> None:
        newest = max(_ts(row) for row in rows)
        if newest > self._cursor:
            self._cursor = newest
            await self._redis.set(CURSOR_KEY, str(newest))

    async def _backfill(self, floor: int, last_time: int) -> int:
        """从 ``last_time`` 向旧走页补捞晚于 ``floor`` 的行（游标不动）。

        触及 floor（已入库区间）或页数上限即停；store 过滤 > floor，
        与增量轮询的重复写入由 DO NOTHING 兜底。
        """
        stored = 0
        for _ in range(BACKFILL_MAX_PAGES):
            rows = await self._fetch_page(last_time)
            if not rows:
                break
            fresh = [row for row in rows if _ts(row) > floor]
            if fresh:
                await self._collector.store(fresh)
                stored += len(fresh)
            oldest = min(_ts(row) for row in rows)
            if oldest <= floor:
                break
            last_time = oldest
        return stored

    async def _heartbeat(self) -> None:
        await self._redis.set(HEARTBEAT_KEY, str(int(time.time())), ex=HEARTBEAT_TTL)

    async def _wait(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    async def run(self) -> None:
        """主循环：自举游标 → 预热会话 → 轮询直到收到停止信号。"""
        self._cursor = await self.load_cursor()
        logger.info("cls_stream_started", cursor=self._cursor)
        await run_in_thread(warm_session)
        while not self._stop.is_set():
            try:
                stored = await self.poll_once()
                self._backoff = BACKOFF_INITIAL
                if stored:
                    logger.info("cls_stream_stored", stored=stored, cursor=self._cursor)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                delay = self._backoff
                self._backoff = min(self._backoff * 2, BACKOFF_MAX)
                logger.error("cls_stream_poll_failed", error=str(exc), retry_in=delay)
                # Cookie 可能已被 WAF 作废：丢弃会话重预热后再退避重试
                reset_session()
                try:
                    await run_in_thread(warm_session)
                except Exception:  # noqa: BLE001
                    logger.warning("cls_stream_rewarm_failed")
                await self._wait(delay)
                continue
            await self._wait(self.poll_interval)
        logger.info("cls_stream_stopped")

    async def close(self) -> None:
        """释放 DB 引擎与 Redis 连接。"""
        from collector.core.base import dispose_engine

        await dispose_engine()
        await self._redis.aclose()


def main() -> None:
    configure_logging()
    from collector.core.config import redis_url

    stream = ClsTelegraphStream(
        ClsTelegraphCollector({"source": "cls", "data_type": "news_telegraph"}),
        redis_async.from_url(redis_url, decode_responses=True),
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stream.request_stop)
        except NotImplementedError:  # pragma: no cover - 非 POSIX 平台
            signal.signal(sig, lambda *_: stream.request_stop())
    try:
        loop.run_until_complete(stream.run())
    finally:
        loop.run_until_complete(stream.close())
        asyncio.set_event_loop(None)
        loop.close()


if __name__ == "__main__":
    main()
