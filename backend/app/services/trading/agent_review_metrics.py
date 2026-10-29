"""多周期复盘确定性指标（B2）：系统计算、LLM 只解读。

指标集与口径（docs/requirement/09 §4.5），全部可由来库数据复算：

- 区间收益率 = (期末调整净值 / 期初调整净值 - 1) × 100；调整净值 = nav − cum_inout，
  剔除出入金对净值的扰动；期初取窗口前最近一条快照，缺失时退回窗口内首条。
- 年化收益 = (1 + 区间收益率) ^ (252 / 窗口交易日数) − 1。
- 最大回撤 = max((峰值 − 调整净值) / 峰值) × 100（期初基准点 + 窗口内逐日）。
- 胜率 = 盈利卖出笔数 / 卖出笔数 × 100；卖出已实现盈亏按移动加权成本、
  手续费计入成本/冲减收益。
- 盈亏比 = 盈利卖出平均盈亏 / |亏损卖出平均盈亏|（无亏损样本时无定义返回 None）。
- 换手率 = 窗口内成交金额合计 / 日均调整净值 × 100。
- 执行偏差率 = 偏离计划成交笔数 / 成交笔数 × 100：无当日同方向计划，或买入价
  落在计划买入区间之外（区间两档都存在时）即视为偏离。
- 相对基准超额 = 区间收益率 − 沪深300 同区间收益率。

计算结果只读落库数据，不写库；``compute_window_metrics`` 负责取数并委托
``build_metrics``（纯函数，单测入口）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import BENCHMARK_INDEX_CODE
from app.models.kline import KlineDaily
from app.models.paper_trade import PaperTradeCashSnapshot, PaperTradeExecution
from app.services.trading.agent_review_periods import ReviewWindow
from app.services.trading.paper_trade_converters import (
    SIDE_BUY,
    SIDE_SELL,
    bare_stock_code,
    to_decimal,
)

#: 期初净值 / 基准收盘的回看天数（覆盖长假与停牌，不必精确到交易日）
_LOOKBACK_DAYS = 30

#: 年化换算的 A 股年交易日数
_TRADING_DAYS_PER_YEAR = 252

#: 计划方向 → 成交方向（关键交易判定与执行偏差共用）
PLAN_SIDE = {"buy": SIDE_BUY, "sell": SIDE_SELL}


@dataclass(frozen=True)
class ExecutionRecord:
    """成交回报的指标消费视图（含账户全历史，用于卖出成本还原）。"""

    trade_date: date
    stock_code: str
    side: int | None
    price: Decimal | None
    volume: int
    turnover: Decimal | None
    commission: Decimal | None
    cl_ord_id: str | None = None


@dataclass(frozen=True)
class PlanRecord:
    """交易计划的指标消费视图（执行偏差与买入区间判定）。"""

    plan_date: date
    stock_code: str
    plan_type: str
    buy_zone_low: Decimal | None
    buy_zone_high: Decimal | None


@dataclass(frozen=True)
class RealizedTrade:
    """一笔已实现的卖出盈亏（移动加权成本口径）。"""

    trade_date: date
    stock_code: str
    profit: Decimal
    cl_ord_id: str | None = None


@dataclass(frozen=True)
class ReviewMetrics:
    """窗口确定性指标集合；不可计算项为 None 并由 notes 说明原因。"""

    period: str
    start_date: date
    end_date: date
    trading_days: int
    covered_start: date | None
    covered_end: date | None
    start_value: float | None
    end_value: float | None
    return_pct: float | None
    annualized_return_pct: float | None
    max_drawdown_pct: float | None
    sell_count: int
    win_rate_pct: float | None
    profit_loss_ratio: float | None
    turnover_rate_pct: float | None
    execution_deviation_pct: float | None
    benchmark_return_pct: float | None
    excess_return_pct: float | None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """wire/LLM 输入用字典（日期转 ISO，None 原样保留）。"""
        return {
            "period": self.period,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "trading_days": self.trading_days,
            "covered_start": self.covered_start.isoformat() if self.covered_start else None,
            "covered_end": self.covered_end.isoformat() if self.covered_end else None,
            "start_value": self.start_value,
            "end_value": self.end_value,
            "return_pct": self.return_pct,
            "annualized_return_pct": self.annualized_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sell_count": self.sell_count,
            "win_rate_pct": self.win_rate_pct,
            "profit_loss_ratio": self.profit_loss_ratio,
            "turnover_rate_pct": self.turnover_rate_pct,
            "execution_deviation_pct": self.execution_deviation_pct,
            "benchmark_return_pct": self.benchmark_return_pct,
            "excess_return_pct": self.excess_return_pct,
            "notes": list(self.notes),
        }


def max_drawdown_pct(values: Sequence[Decimal]) -> float | None:
    """最大回撤（正数百分比）；序列为空或峰值非正时返回 None。"""
    peak: Decimal | None = None
    worst = Decimal("0")
    for value in values:
        if peak is None or value > peak:
            peak = value
            continue
        if peak > 0:
            drawdown = (peak - value) / peak * 100
            if drawdown > worst:
                worst = drawdown
    if peak is None:
        return None
    return round(float(worst), 2)


def annualized_return_pct(
    total_return_pct: float | None, trading_days: int
) -> float | None:
    """年化收益（复利 252 交易日）；亏损超过 100% 或交易日不足时返回 None。"""
    if total_return_pct is None or trading_days <= 0:
        return None
    growth = 1 + total_return_pct / 100
    if growth <= 0:
        return None
    annualized = (growth ** (_TRADING_DAYS_PER_YEAR / trading_days) - 1) * 100
    return round(float(annualized), 2)


def _window_endpoints(
    points: Sequence[tuple[date, Decimal]], start: date, end: date
) -> tuple[Decimal | None, Decimal | None]:
    """窗口期初/期末值：期初取窗口前最近一点，缺失退回窗口内首点。"""
    base: Decimal | None = None
    last: Decimal | None = None
    for day, value in sorted(points, key=lambda item: item[0]):
        if day < start:
            base = value
        elif day <= end:
            if base is None:
                base = value
            last = value
    return base, last


def window_return_pct(
    points: Sequence[tuple[date, Decimal]], start: date, end: date
) -> float | None:
    """区间收益率（百分比）；期初值非正或任一端点缺失时返回 None。"""
    base, last = _window_endpoints(points, start, end)
    if base is None or last is None or base <= 0:
        return None
    return round(float(last / base - 1) * 100, 2)


def realized_trades(
    executions: Sequence[ExecutionRecord], *, start: date, end: date
) -> list[RealizedTrade]:
    """按移动加权成本重放成交，返回窗口内卖出的已实现盈亏。

    输入须覆盖账户自首笔成交起的全部成交（卖出成本还原依赖窗口前持仓），
    按 (交易日, 输入顺序) 依次应用；无价格或方向未知的回报跳过。
    """
    positions: dict[str, tuple[int, Decimal]] = {}
    trades: list[RealizedTrade] = []
    for execution in sorted(executions, key=lambda item: item.trade_date):
        volume = max(execution.volume, 0)
        if execution.price is None or volume <= 0:
            continue
        held, cost = positions.get(execution.stock_code, (0, Decimal("0")))
        if execution.side == SIDE_BUY:
            fee = execution.commission or Decimal("0")
            positions[execution.stock_code] = (
                held + volume,
                cost + execution.price * volume + fee,
            )
            continue
        if execution.side != SIDE_SELL or held <= 0:
            continue
        sold = min(volume, held)
        avg_cost = cost / held
        fee = (execution.commission or Decimal("0")) * sold / volume
        remaining = held - sold
        if remaining == 0:
            positions.pop(execution.stock_code)
        else:
            positions[execution.stock_code] = (remaining, cost - avg_cost * sold)
        if start <= execution.trade_date <= end:
            trades.append(
                RealizedTrade(
                    trade_date=execution.trade_date,
                    stock_code=execution.stock_code,
                    profit=execution.price * sold - avg_cost * sold - fee,
                    cl_ord_id=execution.cl_ord_id,
                )
            )
    return trades


def win_rate_pct(trades: Sequence[RealizedTrade]) -> float | None:
    """胜率（盈利卖出笔数占比）；无卖出时返回 None。"""
    if not trades:
        return None
    wins = sum(1 for trade in trades if trade.profit > 0)
    return round(wins / len(trades) * 100, 2)


def profit_loss_ratio(trades: Sequence[RealizedTrade]) -> float | None:
    """盈亏比（盈利平均 / 亏损平均绝对值）；无盈利样本 0.0，无亏损样本 None。"""
    wins = [trade.profit for trade in trades if trade.profit > 0]
    losses = [trade.profit for trade in trades if trade.profit < 0]
    if not wins:
        return 0.0 if losses else None
    if not losses:
        return None
    average_win = sum(wins, Decimal("0")) / len(wins)
    average_loss = abs(sum(losses, Decimal("0")) / len(losses))
    return round(float(average_win / average_loss), 2)


def turnover_rate_pct(
    turnover: Decimal, average_value: Decimal | None
) -> float | None:
    """换手率（成交金额 / 日均资产）；日均资产非正时返回 None。"""
    if average_value is None or average_value <= 0:
        return None
    return round(float(turnover / average_value * 100), 2)


def is_deviated_execution(
    execution: ExecutionRecord, plans: dict[tuple[date, str, int | None], PlanRecord]
) -> bool:
    """单笔成交是否偏离计划：无当日同方向计划，或买入价在计划区间外。"""
    plan = plans.get(
        (execution.trade_date, execution.stock_code, execution.side)
    )
    if plan is None:
        return True
    if (
        execution.side == SIDE_BUY
        and execution.price is not None
        and plan.buy_zone_low is not None
        and plan.buy_zone_high is not None
    ):
        return not (plan.buy_zone_low <= execution.price <= plan.buy_zone_high)
    return False


def execution_deviation_pct(
    executions: Sequence[ExecutionRecord], plans: Sequence[PlanRecord]
) -> float | None:
    """执行偏差率（偏离计划成交占比）；窗口内无成交时返回 None。"""
    if not executions:
        return None
    index = {
        (plan.plan_date, plan.stock_code, PLAN_SIDE.get(plan.plan_type)): plan
        for plan in plans
        if plan.plan_type in PLAN_SIDE
    }
    deviated = sum(1 for execution in executions if is_deviated_execution(execution, index))
    return round(deviated / len(executions) * 100, 2)


def _round_money(value: Decimal | None) -> float | None:
    return round(float(value), 2) if value is not None else None


def build_metrics(
    window: ReviewWindow,
    *,
    nav_values: Sequence[tuple[date, Decimal]],
    executions: Sequence[ExecutionRecord],
    plans: Sequence[PlanRecord],
    benchmark_values: Sequence[tuple[date, Decimal]],
) -> ReviewMetrics:
    """由已取数序列计算窗口指标（纯函数）。

    Args:
        window: 已对齐交易日的复盘窗口。
        nav_values: (交易日, 调整净值 nav−cum_inout)，含窗口前最近一点。
        executions: 账户自首笔成交起的全部成交（窗口内用于统计，历史用于成本）。
        plans: 窗口内交易计划。
        benchmark_values: 沪深300 (交易日, 收盘)，含窗口前最近一点。
    """
    start, end = window.start, window.end
    nav_series = sorted(nav_values, key=lambda item: item[0])
    in_window_nav = [item for item in nav_series if start <= item[0] <= end]
    pre_window_nav = [item for item in nav_series if item[0] < start]

    base_value, end_value = _window_endpoints(nav_values, start, end)
    covered_start = in_window_nav[0][0] if in_window_nav else None
    covered_end = in_window_nav[-1][0] if in_window_nav else None

    return_pct = window_return_pct(nav_values, start, end)
    drawdown_series: list[Decimal] = []
    if pre_window_nav:
        drawdown_series.append(pre_window_nav[-1][1])
    drawdown_series.extend(value for _, value in in_window_nav)

    in_window_executions = [
        execution for execution in executions if start <= execution.trade_date <= end
    ]
    turnover = Decimal("0")
    for execution in in_window_executions:
        amount = execution.turnover
        if amount is None and execution.price is not None:
            amount = execution.price * execution.volume
        turnover += amount or Decimal("0")

    average_value = (
        sum(drawdown_series, Decimal("0")) / len(drawdown_series)
        if drawdown_series
        else None
    )
    trades = realized_trades(executions, start=start, end=end)
    benchmark_return = window_return_pct(benchmark_values, start, end)

    notes: list[str] = []
    if window.is_empty:
        notes.append("窗口内无交易日，指标不可计算")
    if not in_window_nav:
        notes.append("窗口内无资金快照，收益率与回撤不可计算")
    elif covered_start is not None and covered_start > start:
        notes.append(
            f"账户资金数据自 {covered_start.isoformat()} 起覆盖"
            f"（窗口起点 {start.isoformat()}），实际覆盖 {len(in_window_nav)} 个交易日"
        )
    if in_window_nav and return_pct is None:
        notes.append("期初调整净值非正，区间收益率不可计算")
    if benchmark_return is None:
        notes.append("沪深300 基准行情缺失，超额收益不可计算")

    return ReviewMetrics(
        period=window.period,
        start_date=start,
        end_date=end,
        trading_days=window.trading_day_count,
        covered_start=covered_start,
        covered_end=covered_end,
        start_value=_round_money(base_value),
        end_value=_round_money(end_value),
        return_pct=return_pct,
        annualized_return_pct=annualized_return_pct(
            return_pct, window.trading_day_count
        ),
        max_drawdown_pct=max_drawdown_pct(drawdown_series),
        sell_count=len(trades),
        win_rate_pct=win_rate_pct(trades),
        profit_loss_ratio=profit_loss_ratio(trades),
        turnover_rate_pct=turnover_rate_pct(turnover, average_value),
        execution_deviation_pct=execution_deviation_pct(
            in_window_executions, plans
        ),
        benchmark_return_pct=benchmark_return,
        excess_return_pct=(
            round(return_pct - benchmark_return, 2)
            if return_pct is not None and benchmark_return is not None
            else None
        ),
        notes=tuple(notes),
    )


async def _load_nav_values(
    session: AsyncSession, account_id: int, start: date, end: date
) -> list[tuple[date, Decimal]]:
    rows = (
        await session.execute(
            select(
                PaperTradeCashSnapshot.trade_date,
                PaperTradeCashSnapshot.nav,
                PaperTradeCashSnapshot.cum_inout,
            )
            .where(
                PaperTradeCashSnapshot.paper_trade_account_id == account_id,
                PaperTradeCashSnapshot.trade_date.between(
                    start - timedelta(days=_LOOKBACK_DAYS), end
                ),
                PaperTradeCashSnapshot.nav.is_not(None),
            )
            .order_by(PaperTradeCashSnapshot.trade_date)
        )
    ).all()
    return [
        (day, Decimal(nav) - (Decimal(cum_inout) if cum_inout is not None else Decimal("0")))
        for day, nav, cum_inout in rows
    ]


async def load_executions(
    session: AsyncSession, account_id: int, end: date
) -> list[ExecutionRecord]:
    rows = (
        await session.execute(
            select(
                PaperTradeExecution.trade_date,
                PaperTradeExecution.symbol,
                PaperTradeExecution.side,
                PaperTradeExecution.price,
                PaperTradeExecution.volume,
                PaperTradeExecution.turnover,
                PaperTradeExecution.commission,
                PaperTradeExecution.cl_ord_id,
            )
            .where(
                PaperTradeExecution.paper_trade_account_id == account_id,
                PaperTradeExecution.trade_date <= end,
            )
            .order_by(
                PaperTradeExecution.trade_date,
                PaperTradeExecution.counter_created_at,
                PaperTradeExecution.id,
            )
        )
    ).all()
    return [
        ExecutionRecord(
            trade_date=trade_date,
            stock_code=bare_stock_code(str(symbol or "")),
            side=side,
            price=to_decimal(price),
            volume=int(volume or 0),
            turnover=to_decimal(turnover),
            commission=to_decimal(commission),
            cl_ord_id=str(cl_ord_id) if cl_ord_id else None,
        )
        for (
            trade_date,
            symbol,
            side,
            price,
            volume,
            turnover,
            commission,
            cl_ord_id,
        ) in rows
    ]


async def load_plans(
    session: AsyncSession, agent_key: str, start: date, end: date
) -> list[PlanRecord]:
    from app.services.trading.agent_plan_ops import list_plans_in_window

    plans = await list_plans_in_window(
        session, agent_key, start_date=start, end_date=end
    )
    return [
        PlanRecord(
            plan_date=plan.plan_date,
            stock_code=plan.stock_code,
            plan_type=plan.plan_type,
            buy_zone_low=to_decimal(plan.buy_zone_low),
            buy_zone_high=to_decimal(plan.buy_zone_high),
        )
        for plan in plans
    ]


async def _load_benchmark_values(
    session: AsyncSession, start: date, end: date
) -> list[tuple[date, Decimal]]:
    rows = (
        await session.execute(
            select(KlineDaily.trade_date, KlineDaily.close)
            .where(
                KlineDaily.stock_code == BENCHMARK_INDEX_CODE,
                KlineDaily.trade_date.between(
                    start - timedelta(days=_LOOKBACK_DAYS), end
                ),
                KlineDaily.close.is_not(None),
            )
            .order_by(KlineDaily.trade_date)
        )
    ).all()
    return [
        (day, Decimal(close))
        for day, close in rows
        if close is not None
    ]


async def compute_window_metrics(
    session: AsyncSession,
    *,
    account_id: int,
    agent_key: str,
    window: ReviewWindow,
) -> ReviewMetrics:
    """取数并计算窗口指标（只读；不触发 LLM、不写库）。"""
    if window.is_empty:
        return build_metrics(
            window,
            nav_values=[],
            executions=[],
            plans=[],
            benchmark_values=[],
        )
    nav_values = await _load_nav_values(session, account_id, window.start, window.end)
    executions = await load_executions(session, account_id, window.end)
    plans = await load_plans(session, agent_key, window.start, window.end)
    benchmark_values = await _load_benchmark_values(
        session, window.start, window.end
    )
    return build_metrics(
        window,
        nav_values=nav_values,
        executions=executions,
        plans=plans,
        benchmark_values=benchmark_values,
    )
