"""历史持仓快照重放（B1）：用成交回报重建每日持仓，补齐快照表上线前的缺口。

多周期复盘（docs/requirement/09-multi-period-review-requirement.md §5）需要
窗口内每日的期初/期末仓位，而 ``paper_trade_position_snapshot`` 是盘后同步新写
的表，历史交易日无行。本模块按成交回报确定性重放：

- 逐交易日按「买入加仓加权成本、卖出按原成本减仓、清零即平仓」维护持仓；
- 收盘价取 ``quote_kline_stock_daily``（停牌/缺 bar 沿用最近一次收盘价，
  从未有过收盘价时退回持仓成本价）；
- ``available_volume`` 按 T+1 口径 = 持仓数量 − 当日买入数量（与盘后同步口径一致）；
- 只补缺失交易日：默认跳过已有快照行的日子（盘后同步写入的真实数据优先），
  ``overwrite=True`` 时才覆盖区间内全部行。

事务边界归调用方之前：本函数自身完成 commit（服务层事务约定）。
"""

from datetime import date
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kline import KlineDaily
from app.models.market_trade_calendar import MarketTradeCalendar
from app.models.paper_trade import PaperTradeExecution, PaperTradePositionSnapshot
from app.services.trading.paper_trade_converters import (
    SIDE_BUY,
    SIDE_SELL,
    bare_stock_code,
    quantize_2dp,
    quantize_4dp,
    to_decimal,
)

logger = structlog.get_logger(__name__)

_MARKET = "cn"


def _fallback_symbol(stock_code: str) -> str:
    """6 位代码 → 掘金 symbol（无成交记录可参照时的兜底）。"""
    if stock_code.startswith("6"):
        return f"SHSE.{stock_code}"
    if stock_code.startswith(("4", "8")):
        return f"BSE.{stock_code}"
    return f"SZSE.{stock_code}"


class _Position:
    __slots__ = ("volume", "cost", "symbol")

    def __init__(self) -> None:
        self.volume = 0
        self.cost = Decimal("0")  # 持仓成本总额（加权平均价的分子）
        self.symbol: str | None = None

    @property
    def avg_price(self) -> Decimal:
        return self.cost / self.volume if self.volume else Decimal("0")


def _apply_executions(
    positions: dict[str, _Position],
    bought_today: dict[str, int],
    executions: list[Any],
) -> None:
    """把单日成交按时间序应用到持仓状态（buy 加权成本 / sell 原成本减仓）。"""
    for execution in executions:
        code = bare_stock_code(str(execution.symbol or ""))
        volume = int(execution.volume or 0)
        if not code or volume <= 0:
            continue
        price = to_decimal(execution.price)
        position = positions.setdefault(code, _Position())
        if execution.symbol:
            position.symbol = str(execution.symbol)
        if execution.side == SIDE_BUY:
            if price is None:
                continue
            position.cost += price * volume
            position.volume += volume
            bought_today[code] = bought_today.get(code, 0) + volume
        elif execution.side == SIDE_SELL:
            if position.volume <= 0:
                continue
            sold = min(volume, position.volume)
            # 卖出不改变成本单价：按当前均价冲减成本
            position.cost -= position.avg_price * sold
            position.volume -= sold
            if position.volume == 0:
                positions.pop(code, None)


def _snapshot_rows(
    positions: dict[str, _Position],
    bought_today: dict[str, int],
    trade_date: date,
    closes: dict[str, Decimal],
    last_close: dict[str, Decimal],
) -> list[dict[str, Any]]:
    """当日持仓 → 快照行（收盘估值 + 权重；空仓日返回空列表）。"""
    rows: list[dict[str, Any]] = []
    for code, position in positions.items():
        symbol = position.symbol or _fallback_symbol(code)
        avg_price = quantize_4dp(position.avg_price)
        last_price = closes.get(code) or last_close.get(code) or avg_price
        if last_price is not None:
            last_close[code] = last_price
        market_value = (
            quantize_2dp(last_price * position.volume) if last_price is not None else None
        )
        profit = (
            quantize_2dp((last_price - position.avg_price) * position.volume)
            if last_price is not None
            else None
        )
        profit_rate = (
            quantize_4dp(profit / (position.avg_price * position.volume) * 100)
            if profit is not None and position.avg_price > 0
            else None
        )
        rows.append(
            {
                "paper_trade_account_id": None,  # 调用方补齐
                "trade_date": trade_date,
                "symbol": symbol,
                "stock_code": code,
                "volume": position.volume,
                "available_volume": max(
                    position.volume - bought_today.get(code, 0), 0
                ),
                "avg_price": avg_price,
                "last_price": last_price,
                "market_value": market_value,
                "profit": profit,
                "profit_rate": profit_rate,
            }
        )
    total_value = sum((row["market_value"] or Decimal("0")) for row in rows)
    for row in rows:
        row["weight"] = (
            quantize_4dp(row["market_value"] / total_value * 100)
            if total_value > 0 and row["market_value"] is not None
            else None
        )
    return rows


async def rebuild_position_snapshots(
    session: AsyncSession,
    *,
    account_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """按成交回报重放指定账户的历史每日持仓快照。

    Args:
        session: 数据库会话（函数内 commit，失败由调用方 rollback）。
        account_id: 模拟盘账户主键。
        start_date: 重放起点；缺省取该账户首笔成交交易日。
        end_date: 重放终点（含）；缺省取最近交易日。
        overwrite: 为 True 时覆盖区间内已有快照行；默认只补缺失交易日。

    Returns:
        摘要 {account_id, start_date, end_date, trading_days, written_days,
        rows_written, skipped_days, reason}。

    Raises:
        ValueError: start_date 晚于 end_date。
    """
    if end_date is None:
        # 延迟 import：market 子域聚合面大，避免与 trading 形成顶层环导入
        from app.services.market import trade_calendar_service

        end_date = await trade_calendar_service.resolve_latest_trade_date(session)

    if start_date is None:
        first = await session.execute(
            select(func.min(PaperTradeExecution.trade_date)).where(
                PaperTradeExecution.paper_trade_account_id == account_id
            )
        )
        start_date = first.scalar()
        if start_date is None:
            return {
                "account_id": account_id,
                "trading_days": 0,
                "written_days": 0,
                "rows_written": 0,
                "skipped_days": 0,
                "reason": "no-executions",
            }
    if start_date > end_date:
        raise ValueError(
            f"start_date {start_date} 晚于 end_date {end_date}"
        )

    day_rows = await session.execute(
        select(MarketTradeCalendar.calendar_date)
        .where(
            MarketTradeCalendar.market == _MARKET,
            MarketTradeCalendar.is_trading.is_(True),
            MarketTradeCalendar.calendar_date.between(start_date, end_date),
        )
        .order_by(MarketTradeCalendar.calendar_date)
    )
    trading_days = list(day_rows.scalars())
    if not trading_days:
        return {
            "account_id": account_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "trading_days": 0,
            "written_days": 0,
            "rows_written": 0,
            "skipped_days": 0,
            "reason": "no-trading-calendar",
        }

    execution_rows = await session.execute(
        select(
            PaperTradeExecution.id,
            PaperTradeExecution.trade_date,
            PaperTradeExecution.symbol,
            PaperTradeExecution.side,
            PaperTradeExecution.price,
            PaperTradeExecution.volume,
            PaperTradeExecution.counter_created_at,
        )
        .where(
            PaperTradeExecution.paper_trade_account_id == account_id,
            PaperTradeExecution.trade_date.between(start_date, end_date),
        )
        .order_by(
            PaperTradeExecution.trade_date,
            PaperTradeExecution.counter_created_at,
            PaperTradeExecution.id,
        )
    )
    executions_by_day: dict[date, list[Any]] = {}
    codes: set[str] = set()
    for execution in execution_rows.all():
        executions_by_day.setdefault(execution.trade_date, []).append(execution)
        code = bare_stock_code(str(execution.symbol or ""))
        if code:
            codes.add(code)

    closes: dict[tuple[str, date], Decimal] = {}
    if codes:
        close_rows = await session.execute(
            select(KlineDaily.stock_code, KlineDaily.trade_date, KlineDaily.close).where(
                KlineDaily.stock_code.in_(codes),
                KlineDaily.trade_date.between(start_date, end_date),
                KlineDaily.close.is_not(None),
            )
        )
        closes = {
            (code, day): value for code, day, value in close_rows.all()
        }

    existing_days: set[date] = set()
    if not overwrite:
        existing_rows = await session.execute(
            select(PaperTradePositionSnapshot.trade_date)
            .where(
                PaperTradePositionSnapshot.paper_trade_account_id == account_id,
                PaperTradePositionSnapshot.trade_date.between(start_date, end_date),
            )
            .distinct()
        )
        existing_days = set(existing_rows.scalars())
    else:
        await session.execute(
            delete(PaperTradePositionSnapshot).where(
                PaperTradePositionSnapshot.paper_trade_account_id == account_id,
                PaperTradePositionSnapshot.trade_date.between(start_date, end_date),
            )
        )

    positions: dict[str, _Position] = {}
    last_close: dict[str, Decimal] = {}
    pending: list[dict[str, Any]] = []
    written_days = 0
    skipped_days = 0
    for day in trading_days:
        bought_today: dict[str, int] = {}
        _apply_executions(positions, bought_today, executions_by_day.get(day, []))
        day_closes = {
            code: value
            for (code, close_day), value in closes.items()
            if close_day == day
        }
        rows = _snapshot_rows(positions, bought_today, day, day_closes, last_close)
        if day in existing_days:
            skipped_days += 1
            continue
        if not rows:
            continue
        for snapshot_row in rows:
            snapshot_row["paper_trade_account_id"] = account_id
        pending.extend(rows)
        written_days += 1

    if pending:
        await session.execute(pg_insert(PaperTradePositionSnapshot).values(pending))
    await session.commit()

    summary = {
        "account_id": account_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "trading_days": len(trading_days),
        "written_days": written_days,
        "rows_written": len(pending),
        "skipped_days": skipped_days,
    }
    logger.info("paper_trade_position_replay_done", **summary)
    return summary
