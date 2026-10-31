"""复盘指标数据类型（纯数据，无副作用）。"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


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
