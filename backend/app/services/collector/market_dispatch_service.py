"""行情补采派发：涨停池 / 炸板池 / 跌停池 / 成交额 / 板块资金流。

任务经队列异步执行（板块资金流受东财限流约束约需 10 分钟）；
涨跌家数（``market_breadth``）为盘中快照，数据源无历史，无法补采。
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.schemas.market import CollectTaskResult
from app.services.market import trade_calendar_service

_BACKFILL_TASKS = (
    "limit-up-pool",
    "broken-pool",
    "limit-down-pool",
    "market-amount",
    "sector-fund-flow",
)


class NonTradingDayError(BadRequestError):
    """指定日期不是交易日。"""


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
        symbols: 可选个股代码列表，追加派发个股日 K 采集任务。
    """
    results = await backfill_trade_date(session, trade_date)

    from collector.runtime.dispatcher import dispatch_collector_task

    await dispatch_collector_task(session, "index-kline", {})
    results.append(
        CollectTaskResult(task="index-kline", status="dispatched", items_collected=0)
    )
    if symbols:
        await dispatch_collector_task(
            session, "kline", {"symbols": list(symbols)}
        )
        results.append(
            CollectTaskResult(task="kline", status="dispatched", items_collected=0)
        )
    return results
