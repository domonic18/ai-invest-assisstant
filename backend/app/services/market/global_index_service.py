"""全球指标最新快照与历史走势读取服务。"""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.constants import GLOBAL_INDEX_CODES, INDEX_TREND_DAYS, KLINE_PERIODS
from app.core.exceptions import BadRequestError
from app.repositories.market import global_index_repository
from app.schemas.market import (
    GlobalIndexHistoryPoint,
    GlobalIndexQuoteResponse,
    IndexKlineBar,
    IndexKlineResponse,
)

# 2s10s 利差为衍生指标：US10Y − US2Y 按 trade_date 对齐求差
_SPREAD_CODE = "US2Y10S"
_SPREAD_LEG_CODES = ("US2Y", "US10Y")
_SPREAD_NAME = "美债10Y-2Y利差"

# 每根聚合 bar 需回看的基础日历天数（含周末节假日冗余）
_PERIOD_LOOKBACK_DAYS = {
    "daily": 2,
    "weekly": 8,
    "monthly": 32,
    "quarterly": 95,
    "yearly": 370,
}


async def get_global_index_quotes(session: AsyncSession) -> list[GlobalIndexQuoteResponse]:
    """启用中的全球指标最新收盘快照（按 sort_order 排序，无数据的代码字段留空）。"""
    configs = await global_index_repository.list_enabled_global_configs(session)
    if not configs:
        return []

    codes = [cfg.index_code for cfg in configs]
    latest = await global_index_repository.map_latest_closes(session, codes)
    trends = await global_index_repository.map_recent_closes(
        session, codes, INDEX_TREND_DAYS
    )

    results: list[GlobalIndexQuoteResponse] = []
    for cfg in configs:
        close, change_pct, trade_date = latest.get(cfg.index_code, (None, None, None))
        results.append(
            GlobalIndexQuoteResponse(
                index_code=cfg.index_code,
                index_name=cfg.index_name,
                close=float(close) if close is not None else None,
                change_pct=float(change_pct) if change_pct is not None else None,
                trade_date=trade_date,
                trend=trends.get(cfg.index_code, []),
            )
        )
    return results


async def get_index_history(
    session: AsyncSession, index_code: str, months: int = 12
) -> list[GlobalIndexHistoryPoint]:
    """全球指标近 N 月收盘走势（升序）。

    ``US2Y10S`` 特例：美债 10Y − 2Y 利差，两腿按 trade_date 对齐求差。
    """
    if index_code == _SPREAD_CODE:
        return await _get_spread_history(session, months)
    if index_code not in GLOBAL_INDEX_CODES:
        raise BadRequestError(f"未知全球指标代码: {index_code}")
    since = today_cn() - timedelta(days=months * 31)
    rows = await global_index_repository.list_closes(session, index_code, since)
    return [
        GlobalIndexHistoryPoint(trade_date=d, close=float(c)) for d, c in rows
    ]


async def _get_spread_history(
    session: AsyncSession, months: int
) -> list[GlobalIndexHistoryPoint]:
    since = today_cn() - timedelta(days=months * 31)
    closes = {
        code: dict(await global_index_repository.list_closes(session, code, since))
        for code in _SPREAD_LEG_CODES
    }
    two_year, ten_year = closes[_SPREAD_LEG_CODES[0]], closes[_SPREAD_LEG_CODES[1]]
    return [
        GlobalIndexHistoryPoint(trade_date=d, close=float(ten_year[d] - two_year[d]))
        for d in sorted(set(two_year) & set(ten_year))
    ]


async def get_global_index_kline(
    session: AsyncSession,
    index_code: str,
    period: str = "daily",
    limit: int = 250,
) -> IndexKlineResponse:
    """全球指标多周期 K 线（trade_date 升序）。

    股指/商品/汇率源含 OHLC；债券收益率（tushare/mof）与 2s10s 利差仅 close，
    open/high/low 为 None，前端退化为收盘线。weekly 及以上周期在 Python 侧按
    自然周/月/季/年聚合，聚合 bar 的 date 取周期内首个交易日。
    """
    if period not in KLINE_PERIODS:
        raise BadRequestError(f"不支持的 K 线周期: {period}")

    if index_code == _SPREAD_CODE:
        name = _SPREAD_NAME
        daily_bars = await _spread_daily_bars(session, limit, period)
    elif index_code in GLOBAL_INDEX_CODES:
        name = GLOBAL_INDEX_CODES[index_code]["name"]
        since = today_cn() - timedelta(days=limit * _PERIOD_LOOKBACK_DAYS[period])
        rows = await global_index_repository.list_daily_bars(
            session, index_code, since
        )
        daily_bars = [
            IndexKlineBar(
                date=row.trade_date,
                open=float(v) if (v := row.open) is not None else None,
                high=float(v) if (v := row.high) is not None else None,
                low=float(v) if (v := row.low) is not None else None,
                close=float(v) if (v := row.close) is not None else None,
                volume=row.volume,
                amount=float(v) if (v := row.amount) is not None else None,
            )
            for row in rows
        ]
    else:
        raise BadRequestError(f"未知全球指标代码: {index_code}")

    bars = daily_bars if period == "daily" else _aggregate_bars(daily_bars, period)
    return IndexKlineResponse(
        code=index_code, name=name, period=period, bars=bars[-limit:]
    )


async def _spread_daily_bars(
    session: AsyncSession, limit: int, period: str
) -> list[IndexKlineBar]:
    """2s10s 利差日线（仅 close，两腿按 trade_date 对齐求差）。"""
    since = today_cn() - timedelta(days=limit * _PERIOD_LOOKBACK_DAYS[period])
    closes = {
        code: dict(await global_index_repository.list_closes(session, code, since))
        for code in _SPREAD_LEG_CODES
    }
    two_year, ten_year = closes[_SPREAD_LEG_CODES[0]], closes[_SPREAD_LEG_CODES[1]]
    return [
        IndexKlineBar(
            date=d,
            open=None,
            high=None,
            low=None,
            close=float(ten_year[d] - two_year[d]),
        )
        for d in sorted(set(two_year) & set(ten_year))
    ]


def _bucket_of(period: str, d: date) -> tuple[int, ...]:
    """bar 归属的自然周/月/季/年桶键（ISO 周，跨年归 ISO 年）。"""
    if period == "weekly":
        iso = d.isocalendar()
        return (iso.year, iso.week)
    if period == "monthly":
        return (d.year, d.month)
    if period == "quarterly":
        return (d.year, (d.month - 1) // 3)
    return (d.year,)


def _aggregate_bars(daily: list[IndexKlineBar], period: str) -> list[IndexKlineBar]:
    """按周期桶聚合日线；OHLC 缺失的源按 close 推导高低开。"""
    grouped: dict[tuple[int, ...], list[IndexKlineBar]] = {}
    for bar in daily:
        grouped.setdefault(_bucket_of(period, bar.date), []).append(bar)

    bars: list[IndexKlineBar] = []
    for chunk in grouped.values():
        closes = [b.close for b in chunk if b.close is not None]
        if not closes:
            continue
        opens = [b.open for b in chunk if b.open is not None]
        highs = [b.high for b in chunk if b.high is not None]
        lows = [b.low for b in chunk if b.low is not None]
        volumes = [b.volume for b in chunk if b.volume is not None]
        amounts = [b.amount for b in chunk if b.amount is not None]
        bars.append(
            IndexKlineBar(
                date=chunk[0].date,
                open=opens[0] if opens else closes[0],
                high=max(highs) if highs else max(closes),
                low=min(lows) if lows else min(closes),
                close=closes[-1],
                volume=sum(volumes) if volumes else None,
                amount=round(sum(amounts), 2) if amounts else None,
            )
        )
    return bars
