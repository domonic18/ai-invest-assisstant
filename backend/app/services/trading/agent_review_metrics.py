"""多周期复盘确定性指标（B2）：取数 + 计算入口，LLM 只解读。

指标口径与纯计算见 ``agent_review_metric_calc``，数据类型见
``agent_review_metric_types``；本模块只负责从落库数据取数并委托计算，
是复盘指标对外的稳定入口（类型与纯函数在此再导出）。
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import BENCHMARK_INDEX_CODE
from app.models.kline import KlineDaily
from app.models.paper_trade import PaperTradeCashSnapshot, PaperTradeExecution
from app.services.trading.agent_review_metric_calc import (
    PLAN_SIDE,
    annualized_return_pct,
    build_metrics,
    execution_deviation_pct,
    is_deviated_execution,
    max_drawdown_pct,
    profit_loss_ratio,
    realized_trades,
    turnover_rate_pct,
    win_rate_pct,
    window_return_pct,
)
from app.services.trading.agent_review_metric_types import (
    ExecutionRecord,
    PlanRecord,
    RealizedTrade,
    ReviewMetrics,
)
from app.services.trading.agent_review_periods import ReviewWindow
from app.services.trading.paper_trade_converters import (
    bare_stock_code,
    to_decimal,
)

#: 期初净值 / 基准收盘的回看天数（覆盖长假与停牌，不必精确到交易日）
_LOOKBACK_DAYS = 30

__all__ = [
    "PLAN_SIDE",
    "ExecutionRecord",
    "PlanRecord",
    "RealizedTrade",
    "ReviewMetrics",
    "annualized_return_pct",
    "build_metrics",
    "compute_window_metrics",
    "execution_deviation_pct",
    "is_deviated_execution",
    "load_executions",
    "load_plans",
    "max_drawdown_pct",
    "profit_loss_ratio",
    "realized_trades",
    "turnover_rate_pct",
    "win_rate_pct",
    "window_return_pct",
]


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
