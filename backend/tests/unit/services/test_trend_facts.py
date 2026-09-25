"""趋势事实纯模块单测：通道四分类、三类拐点（量能确认边界）、周线 M60 门控、文本渲染钉死。

渲染文本 ``trend_facts_summary`` 与提取前 ``index_technical_service._trend_summary``
逐字节一致，此处用例与 test_index_technical_service 的钉死文本互为冗余防线。
"""

from datetime import date, timedelta

import pytest

from app.services.market.trend_facts import (
    CHANNEL_CROSSED,
    CHANNEL_DAMPED,
    CHANNEL_DOWN,
    CHANNEL_INSUFFICIENT,
    CHANNEL_UP,
    TURNING_BREAKOUT,
    TURNING_RISK_BREAK,
    TURNING_SUPPORT_TEST,
    compute_trend_facts,
    trend_facts_summary,
)

pytestmark = pytest.mark.unit


def _bars(
    closes: list[float],
    volumes: list[float] | None = None,
    lows: list[float] | None = None,
) -> list[dict]:
    if volumes is None:
        volumes = [1_000_000.0] * len(closes)
    if lows is None:
        lows = [close - 0.5 for close in closes]
    return [
        {
            "trade_date": f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
            "open": close,
            "high": close + 0.3,
            "low": low,
            "close": close,
            "volume": volume,
        }
        for i, (close, volume, low) in enumerate(zip(closes, volumes, lows))
    ]


# ---------- 通道归属 ----------


def test_empty_bars_return_insufficient_facts() -> None:
    facts = compute_trend_facts([])
    assert facts.channel == CHANNEL_INSUFFICIENT
    assert facts.ma10 is None and facts.ma60 is None
    assert facts.turning_points == ()
    assert trend_facts_summary(facts) == "- 趋势概要：均线数据不足；暂无拐点信号"


def test_short_history_channel_insufficient() -> None:
    facts = compute_trend_facts(_bars([10.0 + 0.1 * i for i in range(30)]))
    assert facts.channel == CHANNEL_INSUFFICIENT
    assert facts.ma10 is not None and facts.ma60 is None
    assert facts.turning_points == ()


def test_channel_up_on_steady_ramp() -> None:
    facts = compute_trend_facts(_bars([10.0 + 0.1 * i for i in range(61)]))
    assert facts.channel == CHANNEL_UP


def test_channel_down_on_steady_decline() -> None:
    facts = compute_trend_facts(_bars([20.0 - 0.1 * i for i in range(61)]))
    assert facts.channel == CHANNEL_DOWN


def test_channel_damped_on_glued_mas() -> None:
    facts = compute_trend_facts(_bars([10.0] * 61))
    assert facts.channel == CHANNEL_DAMPED


def test_channel_crossed_on_dip_between_mas() -> None:
    # 前 20 根 15、中 30 根深跌 3、尾 11 根收复 15：MA10 > MA60 > MA30 非单调
    closes = [15.0] * 20 + [3.0] * 30 + [15.0] * 11
    facts = compute_trend_facts(_bars(closes))
    assert facts.channel == CHANNEL_CROSSED


# ---------- 拐点三型（量能确认） ----------


def test_breakout_on_reclaimed_ma30_with_surge() -> None:
    closes = [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    facts = compute_trend_facts(_bars(closes, volumes))
    assert facts.reclaimed_ma30 is True
    assert facts.volume_ratio == 3.0
    assert facts.turning_points == (TURNING_BREAKOUT,)


def test_breakout_on_new_20d_high_with_surge() -> None:
    # 匀速爬升使 MA30 高于前收（收复不成立），创新高成为唯一突破路径
    closes = [10.0 + 0.05 * i for i in range(60)] + [13.25]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    facts = compute_trend_facts(_bars(closes, volumes))
    assert facts.new_20d_high is True
    assert facts.reclaimed_ma30 is False
    assert facts.turning_points == (TURNING_BREAKOUT,)


def test_unconfirmed_new_high_is_not_turning() -> None:
    closes = [10.0] * 60 + [10.5]
    facts = compute_trend_facts(_bars(closes))
    assert facts.new_20d_high is True
    assert facts.turning_points == ()
    # 文本仍提示假突破风险
    assert "量能未确认，留意假突破" in trend_facts_summary(facts)


def test_risk_break_in_uptrend() -> None:
    closes = [10.0] * 31 + [10.0 + 0.1 * i for i in range(1, 30)] + [9.0]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    facts = compute_trend_facts(_bars(closes, volumes))
    assert facts.channel == CHANNEL_UP
    assert facts.broke_ma30 is True
    assert facts.new_20d_low is True
    assert facts.turning_points == (TURNING_RISK_BREAK,)


def _support_case_closes() -> list[float]:
    return [24.0 - 0.08 * i for i in range(59)] + [19.5, 19.45]


def _support_case_lows() -> list[float]:
    return [close - 0.1 for close in _support_case_closes()]


def test_support_test_near_support_with_shrink() -> None:
    volumes = [1_000_000.0] * 60 + [500_000.0]
    facts = compute_trend_facts(_bars(_support_case_closes(), volumes, _support_case_lows()))
    assert facts.channel == CHANNEL_DOWN
    assert facts.support_price == 19.5
    assert facts.near_support is True
    assert facts.is_volume_floor is True
    assert facts.turning_points == (TURNING_SUPPORT_TEST,)


def test_support_test_requires_volume_shrink() -> None:
    # 位置符合但量比 1.0（非缩量非地量）：不成支撑拐点；
    # 第 46 根挖出更低量，避免平量序列触发 20 日地量标志
    volumes = [1_000_000.0] * 45 + [500_000.0] + [1_000_000.0] * 15
    facts = compute_trend_facts(
        _bars(_support_case_closes(), volumes, _support_case_lows())
    )
    assert facts.near_support is True
    assert facts.is_volume_floor is False
    assert facts.turning_points == ()


# ---------- 量能确认边界（0.7 / 1.3） ----------


def test_volume_surge_boundary_at_1_3() -> None:
    closes = [10.0] * 59 + [9.5, 10.6]
    hit = compute_trend_facts(
        _bars(closes, [1_000_000.0] * 60 + [1_300_000.0])
    )
    assert hit.volume_ratio == 1.3
    assert hit.turning_points == (TURNING_BREAKOUT,)

    miss = compute_trend_facts(
        _bars(closes, [1_000_000.0] * 60 + [1_290_000.0])
    )
    assert miss.reclaimed_ma30 is True
    assert miss.turning_points == ()


def test_volume_shrink_boundary_at_0_7() -> None:
    closes = _support_case_closes()
    lows = _support_case_lows()
    # 第 46 根挖出更低量，避免当日触发 20 日地量，纯测比率边界
    volumes = [1_000_000.0] * 45 + [500_000.0] + [1_000_000.0] * 13 + [1_000_000.0, 700_000.0]
    hit = compute_trend_facts(_bars(closes, volumes, lows))
    assert hit.is_volume_floor is False
    assert hit.volume_ratio == pytest.approx(0.7)
    assert hit.turning_points == (TURNING_SUPPORT_TEST,)

    volumes_miss = (
        [1_000_000.0] * 45 + [500_000.0] + [1_000_000.0] * 13 + [1_000_000.0, 710_000.0]
    )
    miss = compute_trend_facts(_bars(closes, volumes_miss, lows))
    assert miss.is_volume_floor is False
    assert miss.volume_ratio == pytest.approx(0.71)
    assert miss.turning_points == ()


def test_volume_floor_flag() -> None:
    volumes = [5_000_000.0] * 41 + [4_000_000.0] * 19 + [100_000.0]
    facts = compute_trend_facts(_bars([10.0] * 61, volumes))
    assert facts.is_volume_floor is True
    assert facts.volume_ratio == pytest.approx(0.025)


# ---------- 文本渲染（与提取前 _trend_summary 逐字节一致） ----------


def test_summary_breakout_text() -> None:
    closes = [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    summary = trend_facts_summary(compute_trend_facts(_bars(closes, volumes)))
    # MA10 > MA30 > MA60 严格单调 → 上升通道；收盘 10.6 同时满足
    # 「收复 MA30」与「创 20 日新高」，两条突破信号并存
    assert summary == (
        "- 趋势概要：上升通道；"
        "突破拐点：带量收复 MA30（量为 5 日均量的 3.00 倍）；"
        "突破拐点：创 20 日新高（平台突破，量能配合（量为 5 日均量的 3.00 倍））"
    )


def test_summary_new_high_with_confirmed_volume() -> None:
    closes = [10.0 + 0.05 * i for i in range(60)] + [13.25]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    summary = trend_facts_summary(compute_trend_facts(_bars(closes, volumes)))
    assert summary == (
        "- 趋势概要：上升通道；"
        "突破拐点：创 20 日新高（平台突破，量能配合（量为 5 日均量的 3.00 倍））"
    )


def test_summary_risk_break_text() -> None:
    closes = [10.0] * 31 + [10.0 + 0.1 * i for i in range(1, 30)] + [9.0]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    summary = trend_facts_summary(compute_trend_facts(_bars(closes, volumes)))
    assert summary == (
        "- 趋势概要：上升通道；"
        "风险拐点：上升通道中放量跌破 MA30（量为 5 日均量的 3.00 倍），上升动能衰竭观察"
    )


def test_summary_support_test_text() -> None:
    # 第 46 根挖出更低量避免地量标志，让文案走「量仅为…倍」分支
    volumes = [1_000_000.0] * 45 + [400_000.0] + [1_000_000.0] * 14 + [500_000.0]
    summary = trend_facts_summary(
        compute_trend_facts(_bars(_support_case_closes(), volumes, _support_case_lows()))
    )
    assert summary == (
        "- 趋势概要：下降通道；"
        "支撑拐点（触底观察）：临近 60 日前低支撑且量能明显收缩"
        "（量仅为 5 日均量的 0.50 倍），符合「支撑+缩量」触底要件"
    )


def test_has_turning_helper() -> None:
    closes = [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    facts = compute_trend_facts(_bars(closes, volumes))
    assert facts.has_turning(TURNING_BREAKOUT) is True
    assert facts.has_turning(TURNING_RISK_BREAK) is False


# ---------- 周线 M60 门控 ----------


def _weekdaily_bars(
    closes: list[float],
    volumes: list[float] | None = None,
) -> list[dict]:
    """周一至周五排布的 bar（i//5 周 + i%5 日），330 根恰为 66 个 ISO 周。"""
    if volumes is None:
        volumes = [1_000_000.0] * len(closes)
    start = date(2025, 1, 6)  # 周一
    return [
        {
            "date": (start + timedelta(weeks=i // 5, days=i % 5)).isoformat(),
            "open": close,
            "high": close + 0.3,
            "low": close - 0.5,
            "close": close,
            "volume": volume,
        }
        for i, (close, volume) in enumerate(zip(closes, volumes))
    ]


_BELOW_WEEKLY = [20.0] * 269 + [10.0] * 59 + [9.5, 10.6]
_ABOVE_WEEKLY = [2.0] * 269 + [10.0] * 59 + [9.5, 10.6]


def test_breakout_gated_below_weekly_ma60() -> None:
    """日线带量收复 MA30 + 创 20 日新高俱备，但周线 M60 之下突破不成立。"""
    volumes = [1_000_000.0] * 329 + [3_000_000.0]
    facts = compute_trend_facts(_weekdaily_bars(_BELOW_WEEKLY, volumes))
    assert facts.reclaimed_ma30 is True
    assert facts.new_20d_high is True
    # 末 60 周收盘 ≈ 47×20 + 12×10 + 10.6 → 17.8433
    assert facts.weekly_ma60 == pytest.approx(1070.6 / 60)
    assert facts.above_weekly_ma60 is False
    assert facts.turning_points == ()


def test_breakout_stands_above_weekly_ma60() -> None:
    volumes = [1_000_000.0] * 329 + [3_000_000.0]
    facts = compute_trend_facts(_weekdaily_bars(_ABOVE_WEEKLY, volumes))
    assert facts.above_weekly_ma60 is True
    assert facts.turning_points == (TURNING_BREAKOUT,)


def test_weekly_facts_none_when_insufficient_weeks() -> None:
    """不足 60 周（次新股）周线事实为 None，不门控。"""
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    facts = compute_trend_facts(_bars([10.0] * 59 + [9.5, 10.6], volumes))
    assert facts.weekly_ma60 is None
    assert facts.above_weekly_ma60 is None
    assert facts.turning_points == (TURNING_BREAKOUT,)


def test_weekly_aggregation_accepts_trade_date_key() -> None:
    """板块路径 bar 用 trade_date 键，聚合同样生效。"""
    bars = _weekdaily_bars(_ABOVE_WEEKLY)
    for bar in bars:
        bar["trade_date"] = bar.pop("date")
    facts = compute_trend_facts(bars)
    assert facts.weekly_ma60 is not None
    assert facts.above_weekly_ma60 is True
