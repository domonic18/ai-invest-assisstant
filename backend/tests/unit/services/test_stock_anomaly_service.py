"""个股异动检测服务单测：初筛网 + MA60/量价精算矩阵 + 编排。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.market.anomaly_common import (
    CATEGORY_ACCELERATION,
    CATEGORY_BREAKOUT,
    CATEGORY_PULLBACK,
    STOCK_DIM_MA60_BREAKOUT,
    STOCK_DIM_PRICE,
    STOCK_DIM_TURNOVER,
    STOCK_DIM_VOLUME,
    AnomalyInputNotReadyError,
)
from app.services.market.stock_anomaly_service import (
    DEFAULT_STOCK_PARAMS,
    StockDetectionParams,
    evaluate_stock,
    pre_screen_spot,
    run_stock_detection,
)

pytestmark = pytest.mark.unit


def _spot(code: str, **kw: object) -> dict:
    base: dict = {
        "stock_code": code,
        "stock_name": f"股票{code}",
        "close": 10.0,
        "change_pct": 2.0,
        "turnover_rate": 3.0,
    }
    base.update(kw)
    return base


def _bars(
    closes: list[float],
    volumes: list[float] | None = None,
    turnover: float | None = 2.0,
) -> list[dict]:
    if volumes is None:
        volumes = [1_000_000.0] * len(closes)
    return [
        {"date": f"2026-{i:02d}-01", "close": close, "volume": volume, "turnover": turnover}
        for i, (close, volume) in enumerate(zip(closes, volumes), start=1)
    ]


# ---------- 初筛 ----------


def test_pre_screen_catches_price_and_turnover_triggers() -> None:
    rows = [
        _spot("000001", change_pct=7.0),
        _spot("000002", change_pct=1.0, turnover_rate=9.0),
        _spot("000003", change_pct=3.0, turnover_rate=3.0),
    ]
    codes = [row["stock_code"] for row in pre_screen_spot(rows)]
    assert set(codes) == {"000001", "000002"}


def test_pre_screen_sorts_by_pre_score_and_caps() -> None:
    rows = [_spot(f"{i:06d}", change_pct=float(i % 10)) for i in range(300)]
    capped = pre_screen_spot(rows, StockDetectionParams(screen_candidate_cap=50))
    assert len(capped) == 50
    # 预分 = 2×|涨跌幅| + 换手率，涨跌幅 9% 的行排前
    assert capped[0]["change_pct"] == 9.0


# ---------- 精算 ----------


def test_insufficient_history_uses_spot_fallback_and_acceleration() -> None:
    closes = [10.0] * 9 + [11.0]
    volumes = [1_000_000.0] * 9 + [3_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("000001", change_pct=2.0, turnover_rate=9.0)
    )
    assert row is not None
    assert row["ma60"] is None
    assert row["is_above_ma60"] is False
    assert row["ma60_breakout"] is False
    assert set(row["anomaly_types"]) == {STOCK_DIM_VOLUME, STOCK_DIM_TURNOVER}
    # 量比 3.0 → 25 + 换手 9 ≥ 8 → 20；正向变动无 MA60 归入加速
    assert row["strength"] == 45
    assert row["attribution_category"] == CATEGORY_ACCELERATION


def test_insufficient_history_negative_move_is_pullback_downweighted() -> None:
    closes = [10.0] * 9 + [9.0]
    row = evaluate_stock(
        _bars(closes), _spot("000001", change_pct=-7.0, turnover_rate=1.0)
    )
    assert row is not None
    assert set(row["anomaly_types"]) == {STOCK_DIM_PRICE}
    assert row["attribution_category"] == CATEGORY_PULLBACK
    # 15 × 0.7
    assert row["strength"] == 10


def test_ma60_breakout_happy_path() -> None:
    closes = [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("600000", change_pct=2.0, turnover_rate=9.0)
    )
    assert row is not None
    assert row["ma60_breakout"] is True
    assert row["is_above_ma60"] is True
    assert row["volume_ratio"] == 3.0
    assert set(row["anomaly_types"]) == {
        STOCK_DIM_MA60_BREAKOUT,
        STOCK_DIM_VOLUME,
        STOCK_DIM_TURNOVER,
    }
    # 突破 40 + 量比 25 + 换手 20 + 多头背景加成 5
    assert row["strength"] == 90
    assert row["attribution_category"] == CATEGORY_BREAKOUT


def test_revisit_above_ma60_without_breakout_is_acceleration() -> None:
    # 昨日已站上 MA60（无首次突破），当日量比放大
    closes = [10.0] * 59 + [11.0, 11.2]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("600000", change_pct=2.0, turnover_rate=3.0)
    )
    assert row is not None
    assert row["ma60_breakout"] is False
    assert set(row["anomaly_types"]) == {STOCK_DIM_VOLUME}
    # 量比 25 + 多头背景加成 5
    assert row["strength"] == 30
    assert row["attribution_category"] == CATEGORY_ACCELERATION


def test_below_ma60_price_move_is_pullback() -> None:
    closes = [10.0] * 60 + [9.0]
    row = evaluate_stock(
        _bars(closes), _spot("600000", change_pct=7.0, turnover_rate=1.0)
    )
    assert row is not None
    assert row["is_above_ma60"] is False
    assert set(row["anomaly_types"]) == {STOCK_DIM_PRICE}
    assert row["attribution_category"] == CATEGORY_PULLBACK
    assert row["strength"] == 10


def test_no_dim_hit_returns_none() -> None:
    closes = [10.0] * 9 + [10.1]
    assert (
        evaluate_stock(_bars(closes), _spot("000001", change_pct=0.5, turnover_rate=1.0))
        is None
    )


def test_fewer_than_two_bars_returns_none() -> None:
    assert evaluate_stock(_bars([10.0]), _spot("000001", change_pct=9.0)) is None


def test_strength_never_exceeds_cap() -> None:
    closes = [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("600000", change_pct=9.0, turnover_rate=12.0)
    )
    assert row is not None
    assert row["strength"] == 100


def test_custom_params_thresholds() -> None:
    closes = [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    params = StockDetectionParams(volume_ratio=4.0, turnover_pct=15.0)
    row = evaluate_stock(
        _bars(closes, volumes),
        _spot("600000", change_pct=2.0, turnover_rate=9.0),
        params,
    )
    assert row is not None
    # 量比 3.0 < 4、换手 9 < 15 均不命中；有效突破仍需默认量比 ≥ 2 确认成立
    assert row["anomaly_types"] == [STOCK_DIM_MA60_BREAKOUT]
    # 突破 40 + 多头背景加成 5
    assert row["strength"] == 45


def test_default_params_match_doc_thresholds() -> None:
    assert DEFAULT_STOCK_PARAMS.screen_change_pct == 6.0
    assert DEFAULT_STOCK_PARAMS.screen_turnover_pct == 8.0
    assert DEFAULT_STOCK_PARAMS.screen_candidate_cap == 250
    assert DEFAULT_STOCK_PARAMS.price_move_pct == 6.0
    assert DEFAULT_STOCK_PARAMS.volume_ratio == 2.5
    assert DEFAULT_STOCK_PARAMS.turnover_pct == 8.0
    assert DEFAULT_STOCK_PARAMS.breakout_volume_ratio == 2.0


# ---------- 编排 ----------


async def test_run_stock_detection_raises_not_ready_on_empty_spot() -> None:
    session = AsyncMock()
    with pytest.raises(AnomalyInputNotReadyError):
        await run_stock_detection(session, date(2026, 9, 11), [], AsyncMock())
    session.commit.assert_not_awaited()


async def test_run_stock_detection_persists_sorted_and_commits() -> None:
    session = AsyncMock()
    spot = [
        _spot("000001", change_pct=2.0, turnover_rate=9.0),
        _spot("000002", change_pct=8.0, turnover_rate=5.0),
        _spot("000003", change_pct=1.0, turnover_rate=1.0),  # 初筛过滤
    ]
    closes = [10.0] * 9 + [11.0]
    persisted = [
        SimpleNamespace(stock_code="000001"),
        SimpleNamespace(stock_code="000002"),
    ]

    async def _fake_fetch(code: str) -> list[dict] | None:
        return _bars(closes) if code in {"000001", "000002"} else None

    with patch(
        "app.repositories.market.anomaly_repository.upsert_stock_rows",
        AsyncMock(return_value=persisted),
    ) as mock_upsert:
        result = await run_stock_detection(session, date(2026, 9, 11), spot, _fake_fetch)

    assert result == persisted
    rows = mock_upsert.call_args.args[2]
    # 初筛入候选 2 只，000003 被过滤；000001 换手维度（20）强于 000002 涨幅维度（15）
    assert [row["stock_code"] for row in rows] == ["000001", "000002"]
    assert rows[0]["strength"] >= rows[1]["strength"]
    session.commit.assert_awaited_once()
