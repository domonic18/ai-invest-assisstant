"""多周期复盘确定性指标契约测试（§4.5 指标口径与不可计算降级）。"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.services.trading import agent_review_metrics as metrics
from app.services.trading.agent_review_metrics import (
    ExecutionRecord,
    PlanRecord,
    annualized_return_pct,
    build_metrics,
    compute_window_metrics,
    execution_deviation_pct,
    max_drawdown_pct,
    profit_loss_ratio,
    realized_trades,
    turnover_rate_pct,
    win_rate_pct,
    window_return_pct,
)
from app.services.trading.agent_review_periods import ReviewWindow
from app.services.trading.paper_trade_converters import SIDE_BUY, SIDE_SELL

_D = Decimal


def _window(
    *,
    start: date = date(2026, 7, 13),
    end: date = date(2026, 7, 15),
    requested_start: date | None = None,
    requested_end: date | None = None,
    trading_days: tuple[date, ...] | None = None,
) -> ReviewWindow:
    days = trading_days or tuple(
        date(2026, 7, day) for day in range(start.day, end.day + 1)
    )
    return ReviewWindow(
        period="week",
        requested_start=requested_start or start,
        requested_end=requested_end or end,
        start=start,
        end=end,
        trading_days=days,
    )


def _execution(
    day: date,
    *,
    side: int | None,
    price: str | None = "10",
    volume: int = 100,
    turnover: str | None = None,
    commission: str | None = None,
    stock_code: str = "600000",
) -> ExecutionRecord:
    return ExecutionRecord(
        trade_date=day,
        stock_code=stock_code,
        side=side,
        price=_D(price) if price is not None else None,
        volume=volume,
        turnover=_D(turnover) if turnover else None,
        commission=_D(commission) if commission else None,
    )


@pytest.mark.unit
class TestMaxDrawdown:
    def test_peak_to_trough(self) -> None:
        values = [_D(x) for x in (100, 120, 90, 110, 80)]
        assert max_drawdown_pct(values) == 33.33

    def test_monotonic_rise_has_no_drawdown(self) -> None:
        assert max_drawdown_pct([_D(100), _D(110)]) == 0.0

    def test_empty_series(self) -> None:
        assert max_drawdown_pct([]) is None


@pytest.mark.unit
class TestAnnualizedReturn:
    def test_full_year(self) -> None:
        assert annualized_return_pct(10.0, 252) == 10.0

    def test_half_year_doubles_period_return(self) -> None:
        assert annualized_return_pct(5.0, 126) == 10.25

    def test_undefined_cases(self) -> None:
        assert annualized_return_pct(None, 10) is None
        assert annualized_return_pct(10.0, 0) is None
        assert annualized_return_pct(-150.0, 10) is None


@pytest.mark.unit
class TestWindowReturn:
    def test_uses_last_point_before_window_as_base(self) -> None:
        points = [
            (date(2026, 7, 14), _D("100")),
            (date(2026, 7, 15), _D("110")),
        ]
        assert window_return_pct(points, date(2026, 7, 15), date(2026, 7, 15)) == 10.0

    def test_falls_back_to_first_in_window_point(self) -> None:
        points = [
            (date(2026, 7, 15), _D("100")),
            (date(2026, 7, 16), _D("105")),
        ]
        assert window_return_pct(points, date(2026, 7, 15), date(2026, 7, 16)) == 5.0

    def test_non_positive_base_is_undefined(self) -> None:
        points = [
            (date(2026, 7, 14), _D("0")),
            (date(2026, 7, 15), _D("10")),
        ]
        assert window_return_pct(points, date(2026, 7, 15), date(2026, 7, 15)) is None


@pytest.mark.unit
class TestRealizedTrades:
    def test_profit_includes_buy_cost_and_sell_commission(self) -> None:
        executions = [
            _execution(date(2026, 7, 10), side=SIDE_BUY, commission="5"),
            _execution(
                date(2026, 7, 15), side=SIDE_SELL, price="12", commission="6"
            ),
        ]
        trades = realized_trades(
            executions, start=date(2026, 7, 14), end=date(2026, 7, 15)
        )

        assert len(trades) == 1
        # 1200 − (1000 + 5) − 6 = 189
        assert trades[0].profit == _D("189")

    def test_partial_sells_reduce_cost_proportionally(self) -> None:
        executions = [
            _execution(date(2026, 7, 10), side=SIDE_BUY, volume=200),
            _execution(date(2026, 7, 14), side=SIDE_SELL, price="11"),
            _execution(date(2026, 7, 15), side=SIDE_SELL, price="9"),
        ]
        trades = realized_trades(
            executions, start=date(2026, 7, 14), end=date(2026, 7, 15)
        )

        assert [trade.profit for trade in trades] == [_D("100"), _D("-100")]
        assert win_rate_pct(trades) == 50.0
        assert profit_loss_ratio(trades) == 1.0

    def test_ignores_sells_outside_window_and_without_position(self) -> None:
        executions = [
            _execution(date(2026, 7, 10), side=SIDE_SELL),
            _execution(date(2026, 7, 10), side=SIDE_BUY),
            _execution(date(2026, 7, 14), side=SIDE_SELL),
        ]
        trades = realized_trades(
            executions, start=date(2026, 7, 14), end=date(2026, 7, 15)
        )

        assert len(trades) == 1


@pytest.mark.unit
class TestWinRateAndProfitLossRatio:
    def test_empty_trades(self) -> None:
        assert win_rate_pct([]) is None
        assert profit_loss_ratio([]) is None

    def test_no_losses_has_no_ratio(self) -> None:
        trades = [metrics.RealizedTrade(date(2026, 7, 15), "600000", _D("10"))]
        assert win_rate_pct(trades) == 100.0
        assert profit_loss_ratio(trades) is None

    def test_no_wins_has_zero_ratio(self) -> None:
        trades = [metrics.RealizedTrade(date(2026, 7, 15), "600000", _D("-10"))]
        assert win_rate_pct(trades) == 0.0
        assert profit_loss_ratio(trades) == 0.0


@pytest.mark.unit
class TestTurnoverRate:
    def test_ratio(self) -> None:
        assert turnover_rate_pct(_D("2200"), _D("1000")) == 220.0

    def test_undefined_without_assets(self) -> None:
        assert turnover_rate_pct(_D("2200"), None) is None
        assert turnover_rate_pct(_D("2200"), _D("0")) is None


@pytest.mark.unit
class TestExecutionDeviation:
    def test_missing_plan_or_out_of_zone_counts_as_deviation(self) -> None:
        plans = [
            PlanRecord(
                plan_date=date(2026, 7, 15),
                stock_code="600000",
                plan_type="buy",
                buy_zone_low=_D("10"),
                buy_zone_high=_D("11"),
            )
        ]
        executions = [
            _execution(date(2026, 7, 15), side=SIDE_BUY, price="10.5"),
            _execution(date(2026, 7, 15), side=SIDE_BUY, price="12"),
            _execution(date(2026, 7, 15), side=SIDE_SELL, price="10.5"),
        ]

        assert execution_deviation_pct(executions, plans) == 66.67

    def test_no_executions(self) -> None:
        assert execution_deviation_pct([], []) is None


@pytest.mark.unit
class TestBuildMetrics:
    def _nav(self) -> list[tuple[date, Decimal]]:
        return [
            (date(2026, 7, 12), _D("1000")),
            (date(2026, 7, 13), _D("1010")),
            (date(2026, 7, 14), _D("1000")),
            (date(2026, 7, 15), _D("1100")),
        ]

    def test_full_metric_set(self) -> None:
        result = build_metrics(
            _window(),
            nav_values=self._nav(),
            executions=[
                _execution(date(2026, 7, 13), side=SIDE_BUY),
                _execution(date(2026, 7, 15), side=SIDE_SELL, price="12"),
            ],
            plans=[
                PlanRecord(
                    plan_date=date(2026, 7, 13),
                    stock_code="600000",
                    plan_type="buy",
                    buy_zone_low=_D("9"),
                    buy_zone_high=_D("11"),
                )
            ],
            benchmark_values=[
                (date(2026, 7, 12), _D("4000")),
                (date(2026, 7, 15), _D("4080")),
            ],
        )

        assert result.trading_days == 3
        assert result.start_value == 1000.0
        assert result.end_value == 1100.0
        assert result.return_pct == 10.0
        assert result.max_drawdown_pct == 0.99
        assert result.annualized_return_pct is not None
        assert result.sell_count == 1
        assert result.win_rate_pct == 100.0
        # 成交额 1000 + 1200；日均调整净值 1027.5
        assert result.turnover_rate_pct == 214.11
        assert result.execution_deviation_pct == 50.0
        assert result.benchmark_return_pct == 2.0
        assert result.excess_return_pct == 8.0
        assert result.notes == ()

    def test_empty_window_degrades_with_notes(self) -> None:
        empty = ReviewWindow(
            period="week",
            requested_start=date(2026, 7, 13),
            requested_end=date(2026, 7, 13),
            start=date(2026, 7, 13),
            end=date(2026, 7, 13),
            trading_days=(),
        )
        result = build_metrics(
            empty,
            nav_values=[],
            executions=[],
            plans=[],
            benchmark_values=[],
        )

        assert result.trading_days == 0
        assert result.return_pct is None
        assert result.max_drawdown_pct is None
        assert result.annualized_return_pct is None
        assert result.sell_count == 0
        assert any("窗口内无交易日" in note for note in result.notes)

    def test_partial_coverage_is_annotated(self) -> None:
        result = build_metrics(
            _window(),
            nav_values=[
                (date(2026, 7, 14), _D("1000")),
                (date(2026, 7, 15), _D("1100")),
            ],
            executions=[],
            plans=[],
            benchmark_values=[],
        )

        assert result.covered_start == date(2026, 7, 14)
        assert result.return_pct == 10.0
        assert any("自 2026-07-14 起覆盖" in note for note in result.notes)
        assert any("实际覆盖 2 个交易日" in note for note in result.notes)

    def test_missing_benchmark_blocks_excess_return(self) -> None:
        result = build_metrics(
            _window(), nav_values=self._nav(), executions=[], plans=[], benchmark_values=[]
        )

        assert result.benchmark_return_pct is None
        assert result.excess_return_pct is None
        assert any("基准行情缺失" in note for note in result.notes)


@pytest.mark.unit
class TestComputeWindowMetrics:
    @pytest.mark.asyncio
    async def test_loads_series_and_builds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            metrics,
            "_load_nav_values",
            AsyncMock(
                return_value=[
                    (date(2026, 7, 12), _D("1000")),
                    (date(2026, 7, 15), _D("1100")),
                ]
            ),
        )
        monkeypatch.setattr(
            metrics,
            "load_executions",
            AsyncMock(return_value=[_execution(date(2026, 7, 15), side=SIDE_BUY)]),
        )
        monkeypatch.setattr(
            metrics,
            "load_plans",
            AsyncMock(
                return_value=[
                    PlanRecord(
                        plan_date=date(2026, 7, 15),
                        stock_code="600000",
                        plan_type="buy",
                        buy_zone_low=_D("10"),
                        buy_zone_high=_D("11"),
                    )
                ]
            ),
        )
        monkeypatch.setattr(
            metrics,
            "_load_benchmark_values",
            AsyncMock(
                return_value=[
                    (date(2026, 7, 12), _D("4000")),
                    (date(2026, 7, 15), _D("4080")),
                ]
            ),
        )

        result = await compute_window_metrics(
            AsyncMock(), account_id=7, agent_key="short-line", window=_window()
        )

        assert result.return_pct == 10.0
        assert result.benchmark_return_pct == 2.0
        assert result.execution_deviation_pct == 0.0

    @pytest.mark.asyncio
    async def test_empty_window_skips_loading(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loader = AsyncMock()
        monkeypatch.setattr(metrics, "_load_nav_values", loader)
        empty = ReviewWindow(
            period="week",
            requested_start=date(2026, 7, 13),
            requested_end=date(2026, 7, 13),
            start=date(2026, 7, 13),
            end=date(2026, 7, 13),
            trading_days=(),
        )

        result = await compute_window_metrics(
            AsyncMock(), account_id=7, agent_key="short-line", window=empty
        )

        assert result.trading_days == 0
        loader.assert_not_awaited()
