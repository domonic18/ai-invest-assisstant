"""大盘涨跌统计 + 成交额 + 情绪温度。

只读 ``market_breadth`` / ``market_amount`` / ``pool_limit_up_stock``；
不触达数据源，所有数据由采集器交易时段 / 盘后任务预写。
"""

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_amount import MarketAmount
from app.models.market_breadth import MarketBreadth
from app.models.pool_limit_up_stock import LimitUpPool
from app.schemas.market import MarketStatsResponse
from app.services.market import index_quotation_service, trade_calendar_service


def _emotion_label(score: float) -> str:
    if score < 20:
        return "冰点"
    if score < 40:
        return "偏冷"
    if score < 60:
        return "温和"
    if score < 80:
        return "偏热"
    return "过热"


def _emotion_score(
    up: int,
    down: int,
    flat: int,
    limit_up: int,
    continuous_rate: float | None,
    broken_rate: float | None,
) -> tuple[float, float]:
    """情绪温度启发式评分（0-100）。

    基准 50 分，按涨跌比、涨停比、连板率、炸板率加权偏移；
    返回 ``(score, 涨停比)``。
    """
    total = max(up + down + flat, 1)
    advance_ratio = up / total
    limit_up_ratio = limit_up / total

    score = 50.0
    score += (advance_ratio - 0.5) * 60
    score += min(limit_up_ratio * 400, 20)
    if continuous_rate is not None:
        score += (continuous_rate - 0.25) * 40
    if broken_rate is not None:
        score += (0.25 - broken_rate) * 40
    return round(min(max(score, 0.0), 100.0), 1), round(limit_up_ratio * 100, 2)


def _breadth_dict(row: MarketBreadth) -> dict[str, Any]:
    return {
        "up_count": row.up_count,
        "down_count": row.down_count,
        "flat_count": row.flat_count,
        "limit_up_count": row.limit_up_count or 0,
        "limit_down_count": row.limit_down_count or 0,
    }


_EMPTY_BREADTH: dict[str, Any] = {
    "up_count": None,
    "down_count": None,
    "flat_count": None,
    "limit_up_count": 0,
    "limit_down_count": 0,
}


async def _pool_limit_up_count(session: AsyncSession, trade_date: date) -> int | None:
    """东财涨停池家数（官方池口径，不含 ST 股）；池未覆盖当日时返回 None。"""
    count = await session.scalar(
        select(func.count())
        .select_from(LimitUpPool)
        .where(LimitUpPool.trade_date == trade_date)
    )
    return count or None


async def _live_breadth(session: AsyncSession, resolved: date) -> dict[str, Any]:
    """当日涨跌统计：取 ``market_breadth`` 不晚于 resolved 的最新一行。

    盘前/周末时最新一行是上一交易日收盘快照；采集器尚未覆盖时返回空统计。
    涨停数在东财涨停池入库后覆盖为池计数。
    """
    row = await session.scalar(
        select(MarketBreadth)
        .where(MarketBreadth.trade_date <= resolved)
        .order_by(MarketBreadth.trade_date.desc())
        .limit(1)
    )
    if row is None:
        return dict(_EMPTY_BREADTH)
    breadth = _breadth_dict(row)
    pool_count = await _pool_limit_up_count(session, row.trade_date)
    if pool_count is not None:
        breadth["limit_up_count"] = pool_count
    return breadth


async def _historical_breadth(
    session: AsyncSession, trade_date: date
) -> dict[str, Any]:
    """历史交易日的涨跌统计。

    优先取 ``market_breadth`` 当日行；该表未覆盖的更早日期回退旧口径：
    涨停数取数据库涨停池，跌停/上涨/下跌/平盘家数返回 None/0。
    """
    row = await session.scalar(
        select(MarketBreadth).where(MarketBreadth.trade_date == trade_date)
    )
    if row is not None and row.limit_up_count is not None:
        breadth = _breadth_dict(row)
        pool_count = await _pool_limit_up_count(session, trade_date)
        if pool_count is not None:
            breadth["limit_up_count"] = pool_count
        return breadth

    limit_up = await _pool_limit_up_count(session, trade_date) or 0
    return {
        "up_count": None,
        "down_count": None,
        "flat_count": None,
        "limit_up_count": limit_up,
        "limit_down_count": (
            row.limit_down_count
            if row is not None and row.limit_down_count is not None
            else 0
        ),
    }


async def _amount_pair(
    session: AsyncSession, resolved: date
) -> tuple[float | None, float | None]:
    """官方成交额（含前一有数据交易日），只读 ``market_amount`` 表。"""
    rows = (
        await session.execute(
            select(MarketAmount)
            .where(MarketAmount.trade_date <= resolved)
            .order_by(MarketAmount.trade_date.desc())
            .limit(2)
        )
    ).scalars().all()
    amount = float(rows[0].amount) if rows and rows[0].amount is not None else None
    prev = (
        float(rows[1].amount)
        if len(rows) > 1 and rows[1].amount is not None
        else None
    )
    return amount, prev


async def _limit_up_rates(
    session: AsyncSession, trade_date: date
) -> tuple[float | None, float | None, int | None]:
    """连板率 / 炸板率 / 炸板家数。

    连板率 = 连板(≥2板)家数 / 涨停总家数；炸板率 = 炸板家数 / (涨停 + 炸板)。
    数据库无当日涨停池时连板率为 None；炸板家数由 ``eastmoney_broken_pool``
    任务盘后写入 ``market_breadth.broken_limit_count``。
    """
    total = await session.scalar(
        select(func.count())
        .select_from(LimitUpPool)
        .where(LimitUpPool.trade_date == trade_date)
    ) or 0
    continuous: int | None = None
    if total:
        continuous = await session.scalar(
            select(func.count())
            .select_from(LimitUpPool)
            .where(
                LimitUpPool.trade_date == trade_date,
                LimitUpPool.consecutive_boards >= 2,
            )
        )

    continuous_rate = (
        round(continuous / total, 4)
        if total and continuous is not None
        else None
    )

    broken_limit_count = await session.scalar(
        select(MarketBreadth.broken_limit_count).where(
            MarketBreadth.trade_date == trade_date
        )
    )

    broken_rate = (
        round(broken_limit_count / (total + broken_limit_count), 4)
        if broken_limit_count is not None and total + broken_limit_count > 0
        else None
    )
    return continuous_rate, broken_rate, broken_limit_count


async def get_market_stats(
    session: AsyncSession, trade_date: date | None = None
) -> MarketStatsResponse:
    """涨跌家数、成交额（含环比）与情绪温度。"""
    latest_date = await trade_calendar_service.resolve_latest_trade_date(session)
    resolved = trade_date or latest_date
    is_live = resolved >= latest_date

    if is_live:
        breadth = await _live_breadth(session, resolved)
    else:
        breadth = await _historical_breadth(session, resolved)

    amount, prev_amount = await _amount_pair(session, resolved)
    if amount is None and is_live:
        # 交易所官方数据盘后发布，盘中回退到指数快照成交额估算
        spot = await index_quotation_service._index_spot()
        if spot is None:
            spot = await index_quotation_service._db_index_spot(session)
        amount = sum(
            (item.get("amount") or 0)
            for item in spot
            if item["code"] in ("sh000001", "sz399001")
        ) or None

    amount_change = None
    amount_change_pct = None
    if amount is not None and prev_amount:
        amount_change = round(amount - prev_amount, 2)
        amount_change_pct = round((amount - prev_amount) / prev_amount * 100, 2)

    continuous_rate, broken_rate, broken_limit_count = await _limit_up_rates(
        session, resolved
    )
    score: float | None = None
    limit_up_ratio: float | None = None
    if breadth["up_count"] is not None:
        score, limit_up_ratio = _emotion_score(
            breadth["up_count"],
            breadth["down_count"],
            breadth["flat_count"],
            breadth["limit_up_count"],
            continuous_rate,
            broken_rate,
        )

    return MarketStatsResponse(
        trade_date=resolved,
        amount=amount,
        prev_amount=prev_amount,
        amount_change=amount_change,
        amount_change_pct=amount_change_pct,
        up_count=breadth["up_count"],
        down_count=breadth["down_count"],
        flat_count=breadth["flat_count"],
        limit_up_count=breadth["limit_up_count"],
        limit_down_count=breadth["limit_down_count"],
        broken_limit_count=broken_limit_count,
        emotion_score=score,
        emotion_label=_emotion_label(score) if score is not None else None,
        limit_up_ratio=limit_up_ratio,
        continuous_rate=continuous_rate,
        broken_rate=broken_rate,
    )
