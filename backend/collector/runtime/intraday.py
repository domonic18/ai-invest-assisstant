"""交易 Agent 盘中自主执行驻留进程（``python -m collector.runtime.intraday``）。

批次 8 PR-1（D21/D24）：交易日连续竞价时段按 ``intraday_tick_interval``（默认
60s）驱动 ``agent_intraday_service.run_tick``（L0→L1→观测，shadow 不下单），
尾盘窗口改跑 ``run_tail_check``；业务逻辑全部在服务层，本进程只负责：

- 时段门控：``collector.core.calendar.is_trading_day`` + ``app.core.clock``
  时段谓词；非交易时段长睡至下一窗口入口；
- 行情供给：当日计划标的集合（个位数）直拉 hq.sinajs.cn 批量快照（sina_quote
  cron */5 对 60s tick 太陈旧），指数环境读 Redis ``market:index_spot``；
- 心跳：``collector:stream:intraday_exec:heartbeat``（TTL 120s）供 compose
  healthcheck 判活；失败指数退避 10→600s；SIGINT/SIGTERM 优雅退出。

每日首 tick 为每个 active Agent 开一条 ``kind=intraday_tick`` 的 AgentRun
（次日滚动收口），显著事件（下单/降级）由服务层写入 step，逐 tick 真相在
观测表。``--once`` 忽略时段强制单次 tick（shadow 语义不变），盘外手动验证用。
"""

import argparse
import asyncio
import json
import signal
import time
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from typing import Any

import httpx
import redis.asyncio as redis_async
import structlog

from app.core.clock import CN_TZ, in_tail_check_window, in_trading_session, now_cn, utc_now
from app.core.constants import INTRADAY_EXEC_SOURCE, STREAM_HEARTBEAT_KEY_TEMPLATE
from app.core.database import AsyncSessionLocal, engine
from app.services.trading import agent_intraday_service, agent_registry
from app.services.trading.agent_run_recorder import AgentRunRecorder
from collector.core.async_helpers import run_in_thread
from collector.core.calendar import is_trading_day
from collector.core.logging import configure_logging
from collector.spiders.sina_index_spot import REDIS_KEY as INDEX_SPOT_KEY

logger = structlog.get_logger(__name__)

HEARTBEAT_KEY = STREAM_HEARTBEAT_KEY_TEMPLATE.format(source=INTRADAY_EXEC_SOURCE)
HEARTBEAT_TTL = 120
BACKOFF_INITIAL = 10.0
BACKOFF_MAX = 600.0

_SINA_BASE_URL = "https://hq.sinajs.cn"


def _to_sina_symbol(code: str) -> str:
    """6 位代码 → 新浪符号（6 开头沪市 sh，其余深市 sz）。"""
    return ("sh" if code.startswith("6") else "sz") + code


def fetch_sina_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """批量拉取新浪实时快照（阻塞 IO，经 run_in_thread 调用）。

    返回按 6 位代码键控的 ``{name, price, prev_close, change_pct}``；解析失败
    的条目跳过（tick 对缺行情标的不评判）。
    """
    if not codes:
        return {}
    url = f"{_SINA_BASE_URL}/list={','.join(_to_sina_symbol(c) for c in codes)}"
    resp = httpx.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=10.0)
    resp.encoding = "GB18030"
    quotes: dict[str, dict[str, Any]] = {}
    for line in resp.text.splitlines():
        if "=" not in line or '"' not in line:
            continue
        var, payload = line.split("=", 1)
        code = var.strip().split("_")[-1].lstrip("shz")
        parts = payload.strip().strip(';').strip('"').split(",")
        if len(parts) < 4:
            continue
        try:
            price = float(parts[3])
            prev_close = float(parts[2])
        except ValueError:
            continue
        if price <= 0 or prev_close <= 0:
            continue
        quotes[code] = {
            "name": parts[0],
            "price": price,
            "prev_close": prev_close,
            "change_pct": round((price - prev_close) / prev_close * 100, 2),
        }
    return quotes


async def read_index_spot(redis_client: Any) -> dict[str, Any] | None:
    """读 Redis 指数快照（sina_index_spot 每分钟覆盖；缺失/坏数据返回 None）。"""
    raw = await redis_client.get(INDEX_SPOT_KEY)
    if not raw:
        return None
    try:
        return {"items": json.loads(raw)}
    except json.JSONDecodeError:
        return None


def seconds_until_next_session(now: datetime) -> float:
    """距下一交易时段入口的秒数（非交易时段长睡；时段内返回 0）。"""
    open_at = (
        dt_time(9, 30),
        dt_time(11, 30),
        dt_time(13, 0),
        dt_time(15, 0),
    )
    today = now.date()

    def at(day: date, t: dt_time) -> datetime:
        return datetime.combine(day, t, tzinfo=CN_TZ)

    if now.time() < open_at[0]:
        return (at(today, open_at[0]) - now).total_seconds()
    if open_at[1] <= now.time() < open_at[2]:
        return (at(today, open_at[2]) - now).total_seconds()
    if now.time() >= open_at[3]:
        return (at(today + timedelta(days=1), open_at[0]) - now).total_seconds()
    return 0.0


class IntradayRunner:
    """盘中执行循环：时段门控 + 行情供给 + 心跳 + 按日滚动 AgentRun。"""

    def __init__(self, redis_client: Any, *, tick_interval: float, once: bool = False) -> None:
        self._redis = redis_client
        self._tick_interval = tick_interval
        self._once = once
        self._stop = asyncio.Event()
        self._recorders: dict[str, AgentRunRecorder] = {}
        self._recorder_date: date | None = None

    def request_stop(self) -> None:
        """请求停止（信号处理器调用，协作式退出）。"""
        self._stop.set()

    async def _ensure_recorders(self, session: Any, trade_date: date) -> None:
        """按交易日滚动 AgentRun：换日收口旧会话并为 active Agent 开新会话。"""
        if self._recorder_date == trade_date:
            return
        for recorder in self._recorders.values():
            await recorder.finish(status="success", summary={"window": "day_complete"})
        agents = await agent_registry.get_intraday_agents(session)
        self._recorders = {
            agent.agent_key: AgentRunRecorder(
                agent_key=agent.agent_key,
                kind="intraday_tick",
                trigger="scheduled",
                trade_date=trade_date,
            )
            for agent in agents
        }
        for recorder in self._recorders.values():
            await recorder.start()
        self._recorder_date = trade_date

    async def tick(self, *, force: bool = False) -> dict[str, int] | None:
        """单次 tick：取计划标的行情 → 按时段分派 run_tick / run_tail_check。"""
        now = now_cn()
        trade_date = now.date()
        async with AsyncSessionLocal() as session:
            await self._ensure_recorders(session, trade_date)
            codes = await agent_intraday_service.plan_stock_codes(session, trade_date=trade_date)
            quotes = await run_in_thread(fetch_sina_quotes, sorted(codes)) if codes else {}
            index_snapshot = await read_index_spot(self._redis)
            if in_tail_check_window(now):
                counters = await agent_intraday_service.run_tail_check(
                    session,
                    trade_date=trade_date,
                    now=utc_now(),
                    quotes=quotes,
                    recorders=self._recorders,
                )
                logger.info("intraday_tail_check", **counters)
            else:
                if not force and not in_trading_session(now):
                    return None
                counters = await agent_intraday_service.run_tick(
                    session,
                    trade_date=trade_date,
                    now=utc_now(),
                    quotes=quotes,
                    recorders=self._recorders,
                    index_snapshot=index_snapshot,
                )
                logger.info("intraday_tick", **counters)
        await self._heartbeat()
        return counters

    async def _heartbeat(self) -> None:
        await self._redis.set(HEARTBEAT_KEY, str(int(time.time())), ex=HEARTBEAT_TTL)

    async def _wait(self, delay: float) -> None:
        """等待（分段 ≤60s 并续心跳）：非交易时段长睡也保 healthcheck TTL 存活。"""
        remaining = max(delay, 0.0)
        while remaining > 0 and not self._stop.is_set():
            chunk = min(remaining, 60.0)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=chunk)
                return
            except asyncio.TimeoutError:
                pass
            remaining -= chunk
            await self._heartbeat()

    async def run(self) -> None:
        """主循环：交易时段按 tick 间隔轮询；非交易日/时段长睡至下一入口。"""
        logger.info("intraday_runner_started", tick_interval=self._tick_interval, once=self._once)
        if self._once:
            await self.tick(force=True)
            return
        backoff = BACKOFF_INITIAL
        while not self._stop.is_set():
            now = now_cn()
            if not await run_in_thread(is_trading_day, now.date()):
                # 非交易日：15 分钟分段睡眠至日期滚动（日历进程内缓存，重判廉价）
                await self._wait(900.0)
                continue
            delay = seconds_until_next_session(now)
            if delay > 0:
                await self._wait(min(delay, 900.0))
                continue
            try:
                await self.tick()
                backoff = BACKOFF_INITIAL
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error("intraday_tick_failed", error=str(exc), retry_in=backoff)
                await self._wait(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
                continue
            await self._wait(self._tick_interval)
        logger.info("intraday_runner_stopped")

    async def close(self) -> None:
        """收口当日 AgentRun 并释放引擎与 Redis 连接。"""
        for recorder in self._recorders.values():
            await recorder.finish(status="success", summary={"window": "shutdown"})
        await engine.dispose()
        await self._redis.aclose()


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="交易 Agent 盘中自主执行驻留进程")
    parser.add_argument("--once", action="store_true", help="忽略时段强制单次 tick（盘外验证）")
    args = parser.parse_args()

    from app.core.config import get_settings
    from collector.core.config import redis_url

    runner = IntradayRunner(
        redis_async.from_url(redis_url, decode_responses=True),
        tick_interval=get_settings().intraday_tick_interval,
        once=args.once,
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, runner.request_stop)
        except NotImplementedError:  # pragma: no cover - 非 POSIX 平台
            signal.signal(sig, lambda *_: runner.request_stop())
    try:
        loop.run_until_complete(runner.run())
    finally:
        loop.run_until_complete(runner.close())
        asyncio.set_event_loop(None)
        loop.close()


if __name__ == "__main__":
    main()
