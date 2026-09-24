"""个股异动检测服务单测：趋势拐点维（量能确认）+ 量价维度 + 编排。

拐点维由 trend_facts 判定（与 test_trend_facts.py 的构造同源）；
存量 wire 字段 ma60/is_above_ma60/ma60_breakout 仍按旧口径写入但不计分。
"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.market.anomaly_common import (
    CATEGORY_ACCELERATION,
    CATEGORY_BREAKDOWN,
    CATEGORY_BREAKOUT,
    CATEGORY_PULLBACK,
    STOCK_DIM_BREAKOUT,
    STOCK_DIM_MA60_BREAKOUT,
    STOCK_DIM_PRICE,
    STOCK_DIM_RISK_BREAK,
    STOCK_DIM_SUPPORT_TEST,
    STOCK_DIM_TURNOVER,
    STOCK_DIM_VOLUME,
    AnomalyInputNotReadyError,
)
from app.services.market.stock_anomaly_service import (
    DEFAULT_STOCK_PARAMS,
    StockDetectionParams,
    evaluate_stock,
    get_stock_anomaly_board,
    pre_screen_spot,
    run_stock_detection,
)
from app.services.market.trend_facts import CHANNEL_UP

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
    low_gap: float = 0.5,
) -> list[dict]:
    if volumes is None:
        volumes = [1_000_000.0] * len(closes)
    return [
        {
            "date": f"2026-{i // 28 + 1:02d}-{i % 28 + 1:02d}",
            "open": close,
            "high": close + 0.3,
            "low": close - low_gap,
            "close": close,
            "volume": volume,
            "turnover": turnover,
        }
        for i, (close, volume) in enumerate(zip(closes, volumes))
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


def test_insufficient_history_volume_turnover_is_acceleration() -> None:
    closes = [10.0] * 9 + [11.0]
    volumes = [1_000_000.0] * 9 + [3_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("000001", change_pct=2.0, turnover_rate=9.0)
    )
    assert row is not None
    assert row["ma60"] is None
    assert row["is_above_ma60"] is False
    assert row["ma60_breakout"] is False
    assert row["trend_facts"]["channel"] == "均线数据不足"
    assert row["trend_facts"]["turning_points"] == ()
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


def test_breakout_turning_full_score_with_up_channel_bonus() -> None:
    # 前收 9.5 跌破后带量收复 MA30 且创 20 日新高：突破拐点 + 量比 + 换手
    closes = [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("600000", change_pct=2.0, turnover_rate=9.0)
    )
    assert row is not None
    assert STOCK_DIM_BREAKOUT in row["anomaly_types"]
    assert row["trend_facts"]["channel"] == CHANNEL_UP
    assert row["trend_facts"]["turning_points"] == ("breakout",)
    assert row["volume_ratio"] == 3.0
    # 存量 wire 字段仍按旧口径写入
    assert row["ma60_breakout"] is True
    assert row["is_above_ma60"] is True
    # 突破 40 + 量比 25 + 换手 20 + 上升通道加成 5
    assert row["strength"] == 90
    assert row["attribution_category"] == CATEGORY_BREAKOUT


def test_risk_break_turning_is_breakdown_not_downweighted() -> None:
    # 上升通道中放量跌破 MA30：风险拐点 30 + 量比 25 + 换手 20 + 加成 5
    closes = [10.0] * 31 + [10.0 + 0.1 * i for i in range(1, 30)] + [9.0]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("600000", change_pct=2.0, turnover_rate=9.0)
    )
    assert row is not None
    assert STOCK_DIM_RISK_BREAK in row["anomaly_types"]
    assert row["trend_facts"]["channel"] == CHANNEL_UP
    assert row["trend_facts"]["turning_points"] == ("risk_break",)
    assert row["is_above_ma60"] is False
    assert row["ma60_breakout"] is False
    assert row["strength"] == 80
    assert row["attribution_category"] == CATEGORY_BREAKDOWN


def test_support_test_turning_near_60d_low_with_shrink() -> None:
    # 下降通道回踩 60 日支撑带 + 20 日地量：支撑拐点 25，反抽弱信号 ×0.7
    closes = [24.0 - 0.08 * i for i in range(59)] + [19.5, 19.45]
    volumes = [1_000_000.0] * 60 + [500_000.0]
    row = evaluate_stock(
        _bars(closes, volumes, low_gap=0.1),
        _spot("600000", change_pct=-1.0, turnover_rate=1.0),
    )
    assert row is not None
    assert row["anomaly_types"] == [STOCK_DIM_SUPPORT_TEST]
    assert row["trend_facts"]["turning_points"] == ("support_test",)
    assert row["attribution_category"] == CATEGORY_PULLBACK
    assert row["strength"] == round(25 * 0.7)


def test_unconfirmed_new_high_does_not_hit_breakout() -> None:
    # 创 20 日新高但无量能确认（量比 1.0）：拐点不成立，量价维也未触发
    closes = [10.0] * 60 + [10.5]
    assert (
        evaluate_stock(
            _bars(closes), _spot("600000", change_pct=0.5, turnover_rate=3.0)
        )
        is None
    )


def test_breakout_on_new_high_only_surge_below_volume_gate() -> None:
    # 量比 2.0：达到拐点量能确认（≥1.3）但未达量比维（≥2.5），仅突破维命中
    closes = [10.0] * 60 + [10.6]
    volumes = [1_000_000.0] * 60 + [2_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("600000", change_pct=2.0, turnover_rate=3.0)
    )
    assert row is not None
    assert row["anomaly_types"] == [STOCK_DIM_BREAKOUT]
    # 突破 40 + 上升通道加成 5
    assert row["strength"] == 45
    assert row["attribution_category"] == CATEGORY_BREAKOUT


def test_below_ma60_down_move_is_pullback() -> None:
    closes = [10.0] * 60 + [9.0]
    row = evaluate_stock(
        _bars(closes), _spot("600000", change_pct=7.0, turnover_rate=1.0)
    )
    assert row is not None
    assert row["is_above_ma60"] is False
    assert row["ma60_breakout"] is False
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
    # 40 + 25 + 20 + 15 + 加成 5 = 105 → 封顶 100
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
    # 量比 3.0 < 4、换手 9 < 15 均不命中；拐点量能确认（≥1.3）独立于量比维
    assert row["anomaly_types"] == [STOCK_DIM_BREAKOUT]
    # 突破 40 + 上升通道加成 5
    assert row["strength"] == 45


def test_default_params_match_doc_thresholds() -> None:
    assert DEFAULT_STOCK_PARAMS.screen_change_pct == 6.0
    assert DEFAULT_STOCK_PARAMS.screen_turnover_pct == 8.0
    assert DEFAULT_STOCK_PARAMS.screen_candidate_cap == 250
    assert DEFAULT_STOCK_PARAMS.price_move_pct == 6.0
    assert DEFAULT_STOCK_PARAMS.volume_ratio == 2.5
    assert DEFAULT_STOCK_PARAMS.turnover_pct == 8.0
    assert DEFAULT_STOCK_PARAMS.breakout_volume_ratio == 2.0


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
            "turnover": 2.0,
        }
        for i, (close, volume) in enumerate(zip(closes, volumes))
    ]


def test_weekly_below_ma60_gates_breakout_dim() -> None:
    """周线 M60 之下：日线带量收复 MA30 不判突破，量价维照常、归加速类。"""
    closes = [20.0] * 269 + [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 329 + [3_000_000.0]
    row = evaluate_stock(
        _weekdaily_bars(closes, volumes),
        _spot("600000", change_pct=2.0, turnover_rate=9.0),
    )
    assert row is not None
    assert row["anomaly_types"] == [STOCK_DIM_VOLUME, STOCK_DIM_TURNOVER]
    assert row["trend_facts"]["above_weekly_ma60"] is False
    assert row["trend_facts"]["turning_points"] == ()
    # 量比 25 + 换手 20 + 上升通道加成 5（日线 MA 多头排列仍在）
    assert row["strength"] == 50
    assert row["attribution_category"] == CATEGORY_ACCELERATION


def test_weekly_above_ma60_keeps_breakout_dim() -> None:
    closes = [2.0] * 269 + [10.0] * 59 + [9.5, 10.6]
    volumes = [1_000_000.0] * 329 + [3_000_000.0]
    row = evaluate_stock(
        _weekdaily_bars(closes, volumes),
        _spot("600000", change_pct=2.0, turnover_rate=9.0),
    )
    assert row is not None
    assert row["anomaly_types"] == [
        STOCK_DIM_BREAKOUT,
        STOCK_DIM_VOLUME,
        STOCK_DIM_TURNOVER,
    ]
    assert row["trend_facts"]["above_weekly_ma60"] is True
    # 突破 40 + 量比 25 + 换手 20 + 加成 5
    assert row["strength"] == 90


def test_legacy_ma60_breakout_wire_field_still_written() -> None:
    # 存量口径：突破日量比 ≥ breakout_volume_ratio 即写 ma60_breakout（不计分）
    closes = [10.0] * 60 + [10.6]
    volumes = [1_000_000.0] * 60 + [2_000_000.0]
    row = evaluate_stock(
        _bars(closes, volumes), _spot("600000", change_pct=2.0, turnover_rate=3.0)
    )
    assert row is not None
    assert row["ma60_breakout"] is True
    assert STOCK_DIM_MA60_BREAKOUT not in row["anomaly_types"]


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


# ---------- 榜单富化 ----------


def _anomaly_row(code: str) -> SimpleNamespace:
    return SimpleNamespace(
        stock_code=code,
        stock_name=f"股票{code}",
        close=10.0,
        change_pct=7.0,
        turnover_rate=9.0,
        volume_ratio=3.0,
        ma60=9.8,
        is_above_ma60=True,
        ma60_breakout=True,
        anomaly_types=[STOCK_DIM_BREAKOUT],
        strength=90,
        attribution_category=CATEGORY_BREAKOUT,
        attribution_summary=None,
    )


async def test_get_board_enriches_sectors_capped_by_change_pct() -> None:
    session = AsyncMock()
    rows = [_anomaly_row("000001"), _anomaly_row("000002")]
    concepts = {"000001": ["融资融券", "算力租赁", "数字经济", "人工智能"]}
    sectors = [
        SimpleNamespace(sector_name="算力租赁", change_pct=5.2),
        SimpleNamespace(sector_name="人工智能", change_pct=-3.0),
        SimpleNamespace(sector_name="融资融券", change_pct=0.4),
    ]

    with (
        patch(
            "app.repositories.market.anomaly_repository.latest_stock_trade_date",
            AsyncMock(return_value=date(2026, 9, 16)),
        ),
        patch(
            "app.repositories.market.anomaly_repository.list_stock_anomalies",
            AsyncMock(return_value=rows),
        ),
        patch("app.services.market.stock_anomaly_service.StockConceptRepository") as mock_repo,
        patch(
            "app.services.market.stock_anomaly_service.sector_quote_repository.list_all_by_date",
            AsyncMock(return_value=sectors),
        ),
    ):
        mock_repo.return_value.get_concepts_by_stocks = AsyncMock(return_value=concepts)
        response = await get_stock_anomaly_board(session, user_id=None)

    assert response is not None
    first = next(it for it in response.items if it.stock_code == "000001")
    # 按 |当日涨幅| 取前 3：算力租赁 5.2 > 人工智能 3.0 > 融资融券 0.4；无涨幅的数字经济被裁
    assert [(s.name, s.change_pct) for s in first.sectors] == [
        ("算力租赁", 5.2),
        ("人工智能", -3.0),
        ("融资融券", 0.4),
    ]
    second = next(it for it in response.items if it.stock_code == "000002")
    assert second.sectors == []


async def test_get_board_returns_none_without_data() -> None:
    session = AsyncMock()
    with patch(
        "app.repositories.market.anomaly_repository.latest_stock_trade_date",
        AsyncMock(return_value=None),
    ):
        assert await get_stock_anomaly_board(session) is None
