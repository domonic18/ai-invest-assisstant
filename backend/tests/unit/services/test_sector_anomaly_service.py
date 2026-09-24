"""板块异动检测服务单测：四维判定（价格/量能/齐动/趋势拐点）+ 强度加权 + 落库编排。

趋势维由 THS 板块日 K 经 trend_facts 判定拐点（量能确认），板块缺 K 线时该维
跳过不抛错；编排用例对 map_sector_kline_by_name 打桩控制趋势输入。
"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.market.anomaly_common import (
    CATEGORY_RESONANCE,
    CATEGORY_ROTATION,
    SECTOR_DIM_PRICE,
    SECTOR_DIM_SYNC,
    SECTOR_DIM_TREND,
    SECTOR_DIM_VOLUME,
    AnomalyInputNotReadyError,
)
from app.services.market.sector_anomaly_service import (
    DEFAULT_SECTOR_PARAMS,
    SectorDetectionParams,
    evaluate_sector,
    run_sector_detection,
)

pytestmark = pytest.mark.unit

_REPO = "app.repositories.market.sector_quote_repository"
_KLINE_REPO = "app.repositories.market.kline_repository"
_UPSERT = "app.repositories.market.anomaly_repository.upsert_sector_rows"
_DELETE_OUTSIDE = "app.repositories.market.anomaly_repository.delete_sector_rows_outside_pool"


# ---------- 四维判定 ----------


def test_all_four_dims_hit_caps_at_100() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=3.5, amount_ratio=2.4, up_count=90, down_count=5, trend_hit=True
    )
    assert dims == [
        SECTOR_DIM_PRICE,
        SECTOR_DIM_VOLUME,
        SECTOR_DIM_SYNC,
        SECTOR_DIM_TREND,
    ]
    # 25 + 15 + 35 + 25 + 多维加成 10 = 110 → 封顶 100
    assert strength == 100
    assert category == CATEGORY_RESONANCE


def test_price_only_is_rotation() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=2.0, amount_ratio=1.1, up_count=50, down_count=45
    )
    assert dims == [SECTOR_DIM_PRICE]
    assert strength == 25
    assert category == CATEGORY_ROTATION


def test_sync_only_is_rotation_with_highest_single_score() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=0.5, amount_ratio=None, up_count=85, down_count=15
    )
    assert dims == [SECTOR_DIM_SYNC]
    assert strength == 35
    assert category == CATEGORY_ROTATION


def test_trend_only_is_rotation() -> None:
    """仅趋势拐点命中（板块 K 线拐点）也构成异动，单维归轮动补涨。"""
    dims, strength, category = evaluate_sector(
        change_pct=1.0, amount_ratio=None, up_count=None, down_count=None, trend_hit=True
    )
    assert dims == [SECTOR_DIM_TREND]
    assert strength == 25
    assert category == CATEGORY_ROTATION


def test_missing_baseline_skips_volume_dim_only() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=2.5, amount_ratio=None, up_count=None, down_count=None
    )
    assert dims == [SECTOR_DIM_PRICE]
    assert strength == 25
    assert category == CATEGORY_ROTATION


def test_down_day_with_price_and_volume_is_resonance() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=-3.0, amount_ratio=2.2, up_count=5, down_count=80
    )
    assert dims == [SECTOR_DIM_PRICE, SECTOR_DIM_VOLUME]
    # 25 + 15 + 加成 10
    assert strength == 50
    assert category == CATEGORY_RESONANCE


def test_sync_ratio_boundary() -> None:
    dims, _, _ = evaluate_sector(
        change_pct=None, amount_ratio=None, up_count=80, down_count=20
    )
    assert dims == [SECTOR_DIM_SYNC]


def test_custom_params_thresholds() -> None:
    # 涨跌幅 3% 与量比 2.5 低于收紧后的阈值，仅齐动性（85/95 ≈ 0.895 ≥ 0.8）命中
    params = SectorDetectionParams(price_move_pct=5.0, volume_ratio=3.0)
    dims, _, _ = evaluate_sector(
        change_pct=3.0, amount_ratio=2.5, up_count=85, down_count=10, params=params
    )
    assert dims == [SECTOR_DIM_SYNC]


def test_no_dim_hit_yields_rotation_with_zero_strength() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=1.0, amount_ratio=1.0, up_count=50, down_count=50
    )
    assert dims == []
    assert strength == 0
    assert category == CATEGORY_ROTATION


# ---------- 编排 ----------


def _snap(sector_type: str, code: str, **kw: object) -> SimpleNamespace:
    base: dict = {
        "sector_type": sector_type,
        "sector_code": code,
        "sector_name": f"板块{code}",
        "change_pct": 3.0,
        "amount": 1.0e9,
        "up_count": 90,
        "down_count": 5,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _kline_row(close: float, volume: float, i: int) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=date(2026, 5, 1) + timedelta(days=i),
        open=close,
        high=close + 0.3,
        low=close - 0.5,
        close=close,
        volume=volume,
    )


def _breakout_bars() -> list[SimpleNamespace]:
    """平台末端带量收复 MA30 的板块日 K（trend_facts 判 breakout 拐点）。"""
    closes = [10.0] * 60 + [10.6]
    volumes = [1_000_000.0] * 60 + [3_000_000.0]
    return [_kline_row(close, volume, i) for i, (close, volume) in enumerate(zip(closes, volumes))]


async def test_run_sector_detection_raises_not_ready_on_empty_snapshot() -> None:
    session = AsyncMock()
    with patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=[])):
        with pytest.raises(AnomalyInputNotReadyError):
            await run_sector_detection(session, date(2026, 9, 11))
    session.commit.assert_not_awaited()


async def test_run_sector_detection_raises_not_ready_on_empty_ths_universe() -> None:
    """THS 指数宇宙为空（板块指数采集未完成）视为输入未就绪。"""
    session = AsyncMock()
    snapshots = [_snap("industry", "BK01")]
    with (
        patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=snapshots)),
        patch(f"{_KLINE_REPO}.list_ths_sector_names", AsyncMock(return_value=[])),
    ):
        with pytest.raises(AnomalyInputNotReadyError):
            await run_sector_detection(session, date(2026, 9, 11))
    session.commit.assert_not_awaited()


async def test_run_sector_detection_persists_and_commits() -> None:
    session = AsyncMock()
    snapshots = [
        _snap("industry", "BK01"),
        _snap("industry", "BK02", change_pct=0.3, up_count=50, down_count=45),
    ]
    persisted = [SimpleNamespace(sector_code="BK01")]
    with (
        patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=snapshots)),
        patch(
            f"{_KLINE_REPO}.list_ths_sector_names",
            AsyncMock(return_value=[("industry", "板块BK01"), ("industry", "板块BK02")]),
        ),
        patch(
            f"{_KLINE_REPO}.map_sector_kline_by_name",
            AsyncMock(return_value={}),
        ),
        patch(
            f"{_KLINE_REPO}.avg_amount_by_sector_name",
            AsyncMock(return_value={("industry", "板块BK01"): (5.0e8, 5)}),
        ),
        patch(
            _DELETE_OUTSIDE,
            AsyncMock(return_value=0),
        ),
        patch(
            _UPSERT,
            AsyncMock(return_value=persisted),
        ) as mock_upsert,
    ):
        result = await run_sector_detection(session, date(2026, 9, 11))

    assert result == persisted
    rows = mock_upsert.call_args.args[2]
    # BK01 三维命中（量比 1.0e9/5.0e8=2.0），BK02 无维度命中被过滤
    assert len(rows) == 1
    row = rows[0]
    assert row["sector_code"] == "BK01"
    assert row["amount_ratio"] == 2.0
    assert row["trend_facts"] is None  # 无板块 K 线：趋势维跳过，落 None
    assert row["strength"] == 85  # 25 + 15 + 35 + 多维加成 10
    assert set(row["anomaly_types"]) == {
        SECTOR_DIM_PRICE,
        SECTOR_DIM_VOLUME,
        SECTOR_DIM_SYNC,
    }
    assert row["attribution_category"] == CATEGORY_RESONANCE
    session.commit.assert_awaited_once()


async def test_run_sector_detection_trend_dim_from_sector_kline() -> None:
    """板块日 K 出拐点：趋势维命中，trend_facts 落 dict，四维加权。"""
    session = AsyncMock()
    snapshots = [_snap("industry", "BK01")]
    with (
        patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=snapshots)),
        patch(
            f"{_KLINE_REPO}.list_ths_sector_names",
            AsyncMock(return_value=[("industry", "板块BK01")]),
        ),
        patch(
            f"{_KLINE_REPO}.map_sector_kline_by_name",
            AsyncMock(return_value={("industry", "板块BK01"): _breakout_bars()}),
        ),
        patch(
            f"{_KLINE_REPO}.avg_amount_by_sector_name",
            AsyncMock(return_value={}),
        ),
        patch(_DELETE_OUTSIDE, AsyncMock(return_value=0)),
        patch(_UPSERT, AsyncMock(return_value=[])) as mock_upsert,
    ):
        await run_sector_detection(session, date(2026, 9, 11))

    rows = mock_upsert.call_args.args[2]
    assert len(rows) == 1
    row = rows[0]
    assert SECTOR_DIM_TREND in row["anomaly_types"]
    assert row["trend_facts"]["turning_points"] == ("breakout",)
    # 价格 25 + 齐动 35 + 趋势 25 + 多维加成 10（量能基线缺失，量能维跳过）
    assert row["strength"] == 95
    assert row["attribution_category"] == CATEGORY_RESONANCE


async def test_run_sector_detection_baseline_gap_skips_volume_dim() -> None:
    session = AsyncMock()
    snapshots = [_snap("industry", "BK01")]
    with (
        patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=snapshots)),
        patch(
            f"{_KLINE_REPO}.list_ths_sector_names",
            AsyncMock(return_value=[("industry", "板块BK01")]),
        ),
        patch(
            f"{_KLINE_REPO}.map_sector_kline_by_name",
            AsyncMock(return_value={}),
        ),
        patch(f"{_KLINE_REPO}.avg_amount_by_sector_name", AsyncMock(return_value={})),
        patch(_DELETE_OUTSIDE, AsyncMock(return_value=0)),
        patch(
            _UPSERT,
            AsyncMock(return_value=[]),
        ) as mock_upsert,
    ):
        await run_sector_detection(session, date(2026, 9, 11))

    rows = mock_upsert.call_args.args[2]
    # 基线窗口不足 5 日：量能维度跳过，涨跌幅 + 齐动性照常判定
    assert len(rows) == 1
    assert SECTOR_DIM_VOLUME not in rows[0]["anomaly_types"]
    assert set(rows[0]["anomaly_types"]) == {SECTOR_DIM_PRICE, SECTOR_DIM_SYNC}
    assert rows[0]["strength"] == 70  # 25 + 35 + 加成 10


async def test_run_sector_detection_baseline_days_short_of_gate_skips_volume_dim() -> None:
    """基线有效天数 < baseline_days 时严格门槛拒绝，量能维度跳过（防零星日期误判放量）。"""
    session = AsyncMock()
    snapshots = [_snap("industry", "BK01")]
    with (
        patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=snapshots)),
        patch(
            f"{_KLINE_REPO}.list_ths_sector_names",
            AsyncMock(return_value=[("industry", "板块BK01")]),
        ),
        patch(
            f"{_KLINE_REPO}.map_sector_kline_by_name",
            AsyncMock(return_value={}),
        ),
        patch(
            f"{_KLINE_REPO}.avg_amount_by_sector_name",
            AsyncMock(return_value={("industry", "板块BK01"): (4.0e8, 4)}),
        ),
        patch(_DELETE_OUTSIDE, AsyncMock(return_value=0)),
        patch(_UPSERT, AsyncMock(return_value=[])) as mock_upsert,
    ):
        await run_sector_detection(session, date(2026, 9, 11))

    rows = mock_upsert.call_args.args[2]
    assert len(rows) == 1
    assert rows[0]["amount_ratio"] is None
    assert SECTOR_DIM_VOLUME not in rows[0]["anomaly_types"]


async def test_run_sector_detection_filters_out_boards_without_ths_match() -> None:
    """检测池收敛：快照中不在 THS 指数宇宙的板块不参与检测，且池外残留被清理。"""
    session = AsyncMock()
    snapshots = [
        _snap("industry", "BK01"),
        _snap("industry", "BK99", change_pct=5.0),  # 二级板块，无同名 THS 指数
    ]
    with (
        patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=snapshots)),
        patch(
            f"{_KLINE_REPO}.list_ths_sector_names",
            AsyncMock(return_value=[("industry", "板块BK01")]),
        ),
        patch(
            f"{_KLINE_REPO}.map_sector_kline_by_name",
            AsyncMock(return_value={}),
        ),
        patch(f"{_KLINE_REPO}.avg_amount_by_sector_name", AsyncMock(return_value={})),
        patch(_DELETE_OUTSIDE, AsyncMock(return_value=1)) as mock_delete,
        patch(_UPSERT, AsyncMock(return_value=[])) as mock_upsert,
    ):
        await run_sector_detection(session, date(2026, 9, 11))

    rows = mock_upsert.call_args.args[2]
    assert [row["sector_code"] for row in rows] == ["BK01"]
    # 清理资格集为「入池快照」全集（BK99 池外残留被删，BK01 即使当日未命中也保留）
    assert mock_delete.call_args.args[2] == {("industry", "BK01")}
    session.commit.assert_awaited_once()


def test_default_params_match_doc_thresholds() -> None:
    assert DEFAULT_SECTOR_PARAMS.price_move_pct == 2.0
    assert DEFAULT_SECTOR_PARAMS.volume_ratio == 2.0
    assert DEFAULT_SECTOR_PARAMS.sync_ratio == 0.8
    assert DEFAULT_SECTOR_PARAMS.baseline_days == 5
