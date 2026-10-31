"""复盘指标纯计算（无 IO；单测直接构造序列断言）。

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
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.services.trading.agent_review_metric_types import (
    ExecutionRecord,
    PlanRecord,
    RealizedTrade,
    ReviewMetrics,
)
from app.services.trading.agent_review_periods import ReviewWindow
from app.services.trading.paper_trade_converters import SIDE_BUY, SIDE_SELL

#: 年化换算的 A 股年交易日数
_TRADING_DAYS_PER_YEAR = 252

#: 计划方向 → 成交方向（关键交易判定与执行偏差共用）
PLAN_SIDE = {"buy": SIDE_BUY, "sell": SIDE_SELL}


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
    if window.warning:
        notes.append(window.warning)
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
