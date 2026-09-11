"""板块异动检测服务单测：三维判定矩阵 + 强度加权 + 落库编排。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.market.anomaly_common import (
    CATEGORY_RESONANCE,
    CATEGORY_ROTATION,
    SECTOR_DIM_PRICE,
    SECTOR_DIM_SYNC,
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


def test_all_three_dims_hit_is_resonance_full_score() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=3.5, amount_ratio=2.4, up_count=90, down_count=5
    )
    assert dims == [SECTOR_DIM_PRICE, SECTOR_DIM_VOLUME, SECTOR_DIM_SYNC]
    # 30 + 20 + 40 + 多维度加成 10
    assert strength == 100
    assert category == CATEGORY_RESONANCE


def test_price_only_is_rotation() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=2.0, amount_ratio=1.1, up_count=50, down_count=45
    )
    assert dims == [SECTOR_DIM_PRICE]
    assert strength == 30
    assert category == CATEGORY_ROTATION


def test_sync_only_is_rotation_with_highest_single_score() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=0.5, amount_ratio=None, up_count=85, down_count=15
    )
    assert dims == [SECTOR_DIM_SYNC]
    assert strength == 40
    assert category == CATEGORY_ROTATION


def test_missing_baseline_skips_volume_dim_only() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=2.5, amount_ratio=None, up_count=None, down_count=None
    )
    assert dims == [SECTOR_DIM_PRICE]
    assert strength == 30
    assert category == CATEGORY_ROTATION


def test_down_day_with_price_and_volume_is_resonance() -> None:
    dims, strength, category = evaluate_sector(
        change_pct=-3.0, amount_ratio=2.2, up_count=5, down_count=80
    )
    assert dims == [SECTOR_DIM_PRICE, SECTOR_DIM_VOLUME]
    # 30 + 20 + 加成 10
    assert strength == 60
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


async def test_run_sector_detection_raises_not_ready_on_empty_snapshot() -> None:
    session = AsyncMock()
    with patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=[])):
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
            f"{_REPO}.recent_trade_dates",
            AsyncMock(return_value=[date(2026, 9, d) for d in (10, 9, 8, 7, 4)]),
        ),
        patch(
            f"{_REPO}.avg_amount_by_sector",
            AsyncMock(return_value={("industry", "BK01"): (5.0e8, 5)}),
        ),
        patch(
            "app.repositories.market.anomaly_repository.upsert_sector_rows",
            AsyncMock(return_value=persisted),
        ) as mock_upsert,
    ):
        result = await run_sector_detection(session, date(2026, 9, 11))

    assert result == persisted
    rows = mock_upsert.call_args.args[2]
    # BK01 三维全中（量比 1.0e9/5.0e8=2.0），BK02 无维度命中被过滤
    assert len(rows) == 1
    row = rows[0]
    assert row["sector_code"] == "BK01"
    assert row["amount_ratio"] == 2.0
    assert row["strength"] == 100
    assert set(row["anomaly_types"]) == {
        SECTOR_DIM_PRICE,
        SECTOR_DIM_VOLUME,
        SECTOR_DIM_SYNC,
    }
    assert row["attribution_category"] == CATEGORY_RESONANCE
    session.commit.assert_awaited_once()


async def test_run_sector_detection_baseline_gap_skips_volume_dim() -> None:
    session = AsyncMock()
    snapshots = [_snap("industry", "BK01")]
    with (
        patch(f"{_REPO}.list_all_by_date", AsyncMock(return_value=snapshots)),
        patch(
            f"{_REPO}.recent_trade_dates",
            AsyncMock(return_value=[date(2026, 9, 10)]),
        ),
        patch(f"{_REPO}.avg_amount_by_sector", AsyncMock(return_value={})),
        patch(
            "app.repositories.market.anomaly_repository.upsert_sector_rows",
            AsyncMock(return_value=[]),
        ) as mock_upsert,
    ):
        await run_sector_detection(session, date(2026, 9, 11))

    rows = mock_upsert.call_args.args[2]
    # 基线窗口不足 5 日：量能维度跳过，涨跌幅 + 齐动性照常判定
    assert len(rows) == 1
    assert SECTOR_DIM_VOLUME not in rows[0]["anomaly_types"]
    assert set(rows[0]["anomaly_types"]) == {SECTOR_DIM_PRICE, SECTOR_DIM_SYNC}


def test_default_params_match_doc_thresholds() -> None:
    assert DEFAULT_SECTOR_PARAMS.price_move_pct == 2.0
    assert DEFAULT_SECTOR_PARAMS.volume_ratio == 2.0
    assert DEFAULT_SECTOR_PARAMS.sync_ratio == 0.8
    assert DEFAULT_SECTOR_PARAMS.baseline_days == 5
