"""行情补采派发：涨停池 / 炸板池 / 跌停池 / 成交额 / 板块资金流 + 个股日 K。

任务经队列异步执行（板块资金流受东财限流约束约需 10 分钟）；
涨跌家数（``market_breadth``）为盘中快照，数据源无历史，无法补采。
个股日 K 采集秒级完成，同步等待终态后返回真实执行结果；
同标的采集仍在执行时复用既有任务，不重复派发。
"""

import asyncio
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.collector_log import CollectorLog
from app.schemas.market import CollectTaskResult
from app.services.market import trade_calendar_service
from app.services.market.trade_calendar_service import NonTradingDayError

_BACKFILL_TASKS = (
    "limit-up-pool",
    "broken-pool",
    "limit-down-pool",
    "market-amount",
    "sector-fund-flow",
)

#: 个股日 K 采集秒级完成：同步等待终态的上限与轮询间隔
_KLINE_WAIT_TIMEOUT_SECONDS = 30.0
_KLINE_WAIT_POLL_INTERVAL_SECONDS = 2.0
_KLINE_RUNNING_STATUSES = frozenset({"pending", "running"})
#: 去重合并窗口：同标的 kline 采集仍在执行时复用既有任务
_KLINE_DEDUP_WINDOW_SECONDS = 600


async def _find_running_kline_log(
    session: AsyncSession, codes: list[str]
) -> CollectorLog | None:
    """窗口内仍在执行且标的集合相交的 kline 采集日志（防重复派发风暴）。"""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_KLINE_DEDUP_WINDOW_SECONDS)
    rows = (
        await session.execute(
            select(CollectorLog)
            .where(
                CollectorLog.task_name == "kline",
                CollectorLog.status.in_(sorted(_KLINE_RUNNING_STATUSES)),
                CollectorLog.started_at >= cutoff,
            )
            .order_by(CollectorLog.id.desc())
            .limit(10)
        )
    ).scalars().all()
    wanted = set(codes)
    for row in rows:
        if wanted & set((row.meta or {}).get("symbols") or []):
            return row
    return None


async def _wait_kline_terminal(log_id: int) -> CollectTaskResult:
    """轮询采集日志到终态（success/failed/partial/skipped），超时如实返回 running。"""
    deadline = time.monotonic() + _KLINE_WAIT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        async with AsyncSessionLocal() as session:
            row = await session.get(CollectorLog, log_id)
        if row is not None and row.status not in _KLINE_RUNNING_STATUSES:
            return CollectTaskResult(
                task="kline",
                status=row.status,
                items_collected=row.records_count or 0,
                message=row.message or row.error_msg or None,
            )
        await asyncio.sleep(_KLINE_WAIT_POLL_INTERVAL_SECONDS)
    return CollectTaskResult(
        task="kline",
        status="running",
        items_collected=0,
        message="个股日 K 补采仍在执行，请稍后用查询工具验证数据",
    )


async def backfill_trade_date(
    session: AsyncSession, trade_date: date
) -> list[CollectTaskResult]:
    """补采指定交易日的行情数据。"""
    if not await trade_calendar_service.is_trading_day(session, trade_date):
        raise NonTradingDayError(
            f"{trade_date.isoformat()} 不是交易日，无法补采数据"
        )

    from collector.runtime.dispatcher import dispatch_collector_task

    results: list[CollectTaskResult] = []
    for task in _BACKFILL_TASKS:
        await dispatch_collector_task(
            session, task, {"trade_date": trade_date.isoformat()}
        )
        results.append(
            CollectTaskResult(task=task, status="dispatched", items_collected=0)
        )
    return results


async def collect_market_data(
    session: AsyncSession,
    trade_date: date,
    symbols: list[str] | None = None,
) -> list[CollectTaskResult]:
    """补采指定交易日行情数据（AI 助手数据自愈入口）：股池/成交额/板块资金流 + 指数 K 线。

    Args:
        symbols: 可选个股代码列表，追加派发个股日 K 采集任务；该任务同步
            等待终态（success/skipped/failed + 入库条数），任意交易日可执行
            （显式 symbols = 手动补采，runner 交易日预检豁免）。
    """
    results = await backfill_trade_date(session, trade_date)
    end_date = trade_date.isoformat()

    from collector.runtime.dispatcher import dispatch_collector_task

    await dispatch_collector_task(session, "index-kline", {"end_date": end_date})
    results.append(
        CollectTaskResult(task="index-kline", status="dispatched", items_collected=0)
    )
    if symbols:
        codes = list(dict.fromkeys(code.strip() for code in symbols if code.strip()))
        running = await _find_running_kline_log(session, codes)
        if running is not None:
            results.append(
                CollectTaskResult(
                    task="kline",
                    status="running",
                    items_collected=0,
                    message="相同标的的补采正在执行，已复用既有任务，请稍后验证数据",
                )
            )
        else:
            log = await dispatch_collector_task(
                session, "kline", {"symbols": codes, "end_date": end_date}
            )
            results.append(await _wait_kline_terminal(log.id))
    return results
