"""长线全市场筛选器单测：周线 M60 硬门槛、次新保留降权、打分排序、Top-N 截断、ST 剔除。"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.trading import long_term_screener
from app.services.trading.long_term_screener import screen_long_term_candidates

pytestmark = pytest.mark.unit

_TRADE_DATE = date(2026, 10, 16)


def _bars(closes: list[float], end_date: date) -> list[MagicMock]:
    """KlineDaily 形状的 ORM 行替身（升序，末日 = end_date，按交易日回推）。"""
    dates: list[date] = []
    d = end_date
    while len(dates) < len(closes):
        if d.weekday() < 5:  # 周一至周五：保证 330 根覆盖 66 个 ISO 周
            dates.append(d)
        d -= timedelta(days=1)
    dates.reverse()
    return [
        MagicMock(
            trade_date=d,
            open=close,
            high=close + 0.3,
            low=close - 0.5,
            close=close,
            volume=1_000_000,
        )
        for d, close in zip(dates, closes)
    ]


def _ramp_closes(n: int = 330) -> list[float]:
    return [10.0 * (1.005**i) for i in range(n)]


def _below_weekly_closes() -> list[float]:
    """330 根：前 269 高位 20、后 61 跌至 10 附近 → 收盘在周线 MA60 之下。"""
    return [20.0] * 269 + [10.0] * 59 + [9.5, 10.6]


def _young_closes() -> list[float]:
    """100 根平盘：周线不足 60 周（次新），不触发硬门槛。"""
    return [10.0] * 100


def _universe_rows() -> list[tuple[str, str]]:
    return [
        ("sh600000", "强势股"),
        ("sz000001", "弱势股"),
        ("sz300001", "次新股"),
        ("sh600519", "ST 冒险"),
    ]


def _bars_payload() -> dict[str, list[MagicMock]]:
    return {
        "sh600000": _bars(_ramp_closes(), _TRADE_DATE),
        "sz000001": _bars(_below_weekly_closes(), _TRADE_DATE),
        "sz300001": _bars(_young_closes(), _TRADE_DATE),
    }


def _session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = _universe_rows()
    session.execute = AsyncMock(return_value=result)
    return session


async def _screen(session: AsyncMock, top_n: int = 30) -> list[dict]:
    with (
        patch.object(
            long_term_screener, "fetch_daily_bars_multi", AsyncMock(return_value=_bars_payload())
        ),
    ):
        return await screen_long_term_candidates(session, _TRADE_DATE, top_n=top_n)


@pytest.mark.asyncio
async def test_below_weekly_ma60_excluded() -> None:
    """周线 M60 之下硬门槛剔除（哪怕日线带量反弹）。"""
    candidates = await _screen(_session())
    codes = [c["stock_code"] for c in candidates]
    assert "sz000001" not in codes


@pytest.mark.asyncio
async def test_st_excluded_from_universe() -> None:
    session = _session()
    candidates = await _screen(session)
    codes = [c["stock_code"] for c in candidates]
    assert "sh600519" not in codes
    # 宇宙查询限定沪/深/北三市场
    stmt = session.execute.await_args_list[0].args[0]
    compiled = str(stmt)
    assert "market IN" in compiled


@pytest.mark.asyncio
async def test_young_stock_kept_but_downweighted() -> None:
    """次新股（周线不足 60 周）保留候选但降权，above_weekly_ma60=None。"""
    candidates = await _screen(_session())
    by_code = {c["stock_code"]: c for c in candidates}
    assert "sz300001" in by_code
    young = by_code["sz300001"]
    assert young["above_weekly_ma60"] is None
    assert young["score"] < 0  # 降权分 -3 后仍为负


@pytest.mark.asyncio
async def test_strong_stock_scores_top() -> None:
    candidates = await _screen(_session())
    assert candidates[0]["stock_code"] == "sh600000"
    top = candidates[0]
    assert top["above_weekly_ma60"] is True
    assert top["four_line_blossom"] is True
    assert top["new_20d_high"] is True
    assert top["channel"] == "上升通道"
    assert top["score"] >= 3.0  # 开花 +2 · 上升通道 +1 · 发散封顶 +2
    assert top["weekly_ma60"] is not None
    assert top["close"] == pytest.approx(_ramp_closes()[-1], abs=0.01)


@pytest.mark.asyncio
async def test_candidates_sorted_by_score_desc() -> None:
    candidates = await _screen(_session())
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_top_n_truncation() -> None:
    candidates = await _screen(_session(), top_n=1)
    assert len(candidates) == 1
    assert candidates[0]["stock_code"] == "sh600000"


@pytest.mark.asyncio
async def test_stale_bars_dropped() -> None:
    """最新日 K 距 trade_date 超 10 天（停牌/退市脏数据）剔除。"""
    payload = _bars_payload()
    stale = _bars(_ramp_closes(), _TRADE_DATE - timedelta(days=15))
    payload["sh600000"] = stale
    with patch.object(
        long_term_screener, "fetch_daily_bars_multi", AsyncMock(return_value=payload)
    ):
        candidates = await screen_long_term_candidates(_session(), _TRADE_DATE)
    assert "sh600000" not in [c["stock_code"] for c in candidates]
