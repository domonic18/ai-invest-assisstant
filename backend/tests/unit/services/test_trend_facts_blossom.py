"""四线开花纯函数单测：多头排列发散 / 不满足 / 次新三态 + TrendFacts 挂载。"""

import pytest

from app.services.market.trend_facts import (
    BLOSSOM_GAP_PCT,
    BLOSSOM_WINDOWS,
    FourLineBlossom,
    blossom_four_lines,
    compute_trend_facts,
)

pytestmark = pytest.mark.unit


def test_young_stock_not_applicable() -> None:
    """日线不足 250 根（次新）applicable=False，各均线 None，不误杀。"""
    blossom = blossom_four_lines([10.0] * (BLOSSOM_WINDOWS[-1] - 1))
    assert blossom == FourLineBlossom(
        applicable=False,
        bloomed=False,
        ma60=None,
        ma120=None,
        ma180=None,
        ma250=None,
        min_gap_pct=None,
    )


def test_exactly_250_bars_is_applicable() -> None:
    blossom = blossom_four_lines([10.0] * BLOSSOM_WINDOWS[-1])
    assert blossom.applicable is True
    assert blossom.bloomed is False  # 全平 → 间距 0，粘合未发散
    assert blossom.min_gap_pct == 0.0


def test_bloomed_on_strong_uptrend() -> None:
    """匀速 0.5%/日爬升：MA60>MA120>MA180>MA250 且间距远超阈值。"""
    closes = [10.0 * (1.005**i) for i in range(300)]
    blossom = blossom_four_lines(closes)
    assert blossom.applicable is True
    assert blossom.bloomed is True
    assert blossom.ma60 > blossom.ma120 > blossom.ma180 > blossom.ma250
    assert blossom.min_gap_pct is not None and blossom.min_gap_pct > 5.0


def test_not_bloomed_when_below_threshold_gap() -> None:
    """多头排列但相邻间距 < 阈值（极缓爬升）：粘合不算开花。"""
    # 0.01%/日爬升 250 根：短窗与长窗均价差仅 ~1%，相邻均线间距 < 0.5%
    closes = [10.0 * (1.0001**i) for i in range(300)]
    blossom = blossom_four_lines(closes)
    assert blossom.applicable is True
    assert blossom.ma60 > blossom.ma120 > blossom.ma180 > blossom.ma250
    assert blossom.bloomed is False
    assert blossom.min_gap_pct is not None and blossom.min_gap_pct < BLOSSOM_GAP_PCT


def test_not_bloomed_on_downtrend() -> None:
    closes = [10.0 * (0.995**i) for i in range(300)]
    blossom = blossom_four_lines(closes)
    assert blossom.applicable is True
    assert blossom.bloomed is False
    assert blossom.ma60 < blossom.ma120


def test_trend_facts_attaches_blossom() -> None:
    bars = [
        {
            "trade_date": f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
            "open": close,
            "high": close + 0.3,
            "low": close - 0.5,
            "close": close,
            "volume": 1_000_000,
        }
        for i, close in enumerate([10.0 * (1.005**j) for j in range(300)])
    ]
    facts = compute_trend_facts(bars)
    assert facts.four_line_blossom is not None
    assert facts.four_line_blossom.bloomed is True


def test_empty_facts_blossom_none() -> None:
    facts = compute_trend_facts([])
    assert facts.four_line_blossom is None
