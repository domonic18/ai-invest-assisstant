"""指数行情：分时 / 实时快照 / 多周期 K 线。

请求路径零直取数据源：
- 实时态：指数快照由 ``sina_index_spot`` 任务每分钟写 Redis（``market:index_spot``）；
- 日内时序：指数分钟线由 ``sina_index_minute`` 任务写 ``quote_kline_stock_minute`` 超表；
- 日频事实：日 K 写 ``quote_kline_stock_daily``，多周期由 TimescaleDB ``time_bucket`` 聚合。
"""

import asyncio
import json
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.constants import INDEX_CODES, KLINE_CHART_EXTRA_CODES
from app.repositories.market.kline_repository import (
    PERIOD_BUCKET,
    fetch_aggregated_bars,
    fetch_daily_bars,
    fetch_minute_bars,
    latest_minute_day,
    prev_minute_close,
)
from app.schemas.market import (
    IndexIntradayPoint,
    IndexIntradayResponse,
    IndexKlineBar,
    IndexKlineResponse,
    IndexQuoteResponse,
)

_INDEX_SPOT_KEY = "market:index_spot"
_TREND_DAYS = 30
_CN_TZ = ZoneInfo("Asia/Shanghai")


async def _index_spot() -> list[dict[str, Any]] | None:
    """采集器写入的指数实时快照；采集器尚未覆盖时为 None。"""
    raw = await get_redis().get(_INDEX_SPOT_KEY)
    return json.loads(raw) if raw else None


async def _local_index_closes(
    session: AsyncSession, code: str, end_date: date | None, limit: int
) -> list[float]:
    """本地 ``quote_kline_stock_daily`` 最近 limit 根收盘（升序）；无数据返回空。"""
    bars = await fetch_daily_bars(session, code, end_date=end_date, limit=limit)
    return [float(bar.close) for bar in reversed(bars) if bar.close is not None]


async def _db_index_spot(session: AsyncSession) -> list[dict[str, Any]]:
    """实时快照缺失时的降级：由 ``quote_kline_stock_daily`` 最近两根日 K 合成行情快照。"""
    quotes: list[dict[str, Any]] = []
    for code, name in INDEX_CODES.items():
        bars = await fetch_daily_bars(session, code, limit=2)
        bars = [bar for bar in bars if bar.close is not None]
        if not bars:
            continue
        latest = bars[0]
        close = float(latest.close)  # type: ignore[arg-type]
        prev = float(bars[1].close) if len(bars) > 1 and bars[1].close else None
        change = round(close - prev, 3) if prev else None
        quotes.append(
            {
                "code": code,
                "name": name,
                "price": close,
                "change": change,
                "change_pct": (
                    round(change / prev * 100, 2) if change is not None and prev
                    else None
                ),
                "amount": (
                    float(latest.amount) if latest.amount is not None else None
                ),
            }
        )
    return quotes


async def get_index_intraday(
    session: AsyncSession, code: str, trade_date: date | None = None
) -> IndexIntradayResponse:
    """指数分时图数据（价格 + 量能），只读 ``quote_kline_stock_minute``。

    默认取表内最近交易日；指定历史日期时取当日分钟序列，无数据抛
    ``ValueError``。昨收优先取前一交易日分钟尾 bar，缺失时回退日 K 收盘。
    """
    if code not in INDEX_CODES:
        raise ValueError(f"不支持的指数代码: {code}")

    target = trade_date or await latest_minute_day(session, code)
    if target is None:
        return IndexIntradayResponse(
            code=code, name=INDEX_CODES[code], trade_date=date.today(),
            prev_close=0.0, points=[],
        )

    bars = await fetch_minute_bars(session, code, target)
    if trade_date is not None and not bars:
        raise ValueError(f"{target.isoformat()} 无分时数据")

    prev_close = await prev_minute_close(session, code, target)
    if prev_close is None:
        daily = await fetch_daily_bars(session, code, end_date=target, limit=2)
        earlier = [bar for bar in daily if bar.trade_date < target and bar.close]
        prev_close = (
            float(earlier[0].close)  # type: ignore[arg-type]
            if earlier
            else None
        )
    if prev_close is None:
        prev_close = float(bars[0].close) if bars and bars[0].close else 0.0

    points = [
        IndexIntradayPoint(
            time=bar.trade_time.astimezone(_CN_TZ).strftime("%H:%M"),
            price=float(bar.close) if bar.close is not None else 0.0,
            volume=float(bar.volume) if bar.volume is not None else 0.0,
            amount=float(bar.amount) if bar.amount is not None else 0.0,
        )
        for bar in bars
    ]
    return IndexIntradayResponse(
        code=code,
        name=INDEX_CODES[code],
        trade_date=target,
        prev_close=prev_close,
        points=points,
    )


async def get_index_quotes(
    session: AsyncSession,
    trade_date: date | None = None,
) -> list[IndexQuoteResponse]:
    """四大指数行情（含近 30 日收盘趋势）。

    默认取采集器写入 Redis 的实时快照（缺失时由日 K 合成）；
    指定历史交易日时从本地 ``quote_kline_stock_daily`` 取当日收盘与涨跌。
    """
    if trade_date is not None:
        quotes = await _historical_index_quotes(session, trade_date)
        if quotes or trade_date < date.today():
            return quotes
        # 当日盘中日线尚未更新，回退实时快照
    spot = await _index_spot()
    if spot is None:
        spot = await _db_index_spot(session)

    trends = [
        await _local_index_closes(session, item["code"], None, _TREND_DAYS)
        for item in spot
    ]
    return [
        IndexQuoteResponse(**item, trend=trend)
        for item, trend in zip(spot, trends, strict=True)
    ]


def _num(value: Any) -> float | None:
    return float(value) if value is not None else None


async def get_index_kline(
    session: AsyncSession,
    code: str,
    period: str = "daily",
    limit: int = 250,
) -> IndexKlineResponse:
    """指数多周期 K 线（升序返回）。

    ``daily`` 直读本地 ``quote_kline_stock_daily``；``weekly/monthly/quarterly/yearly``
    由 TimescaleDB ``time_bucket`` 聚合，聚合周期的 date 取周期首根交易日。
    标的范围：四大指数（``INDEX_CODES``）+ K 线图扩展标的（``KLINE_CHART_EXTRA_CODES``）。
    """
    kline_codes = {**INDEX_CODES, **KLINE_CHART_EXTRA_CODES}
    if code not in kline_codes:
        raise ValueError(f"不支持的指数代码: {code}")

    if period == "daily":
        rows = await fetch_daily_bars(session, code, limit=limit)
        bars = [
            IndexKlineBar(
                date=row.trade_date,
                open=_num(row.open),
                high=_num(row.high),
                low=_num(row.low),
                close=_num(row.close),
                volume=row.volume,
                amount=_num(row.amount),
            )
            for row in reversed(rows)
        ]
    else:
        bucket = PERIOD_BUCKET.get(period)
        if bucket is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        agg_rows = await fetch_aggregated_bars(session, code, bucket, limit=limit)
        bars = [
            IndexKlineBar(
                date=row["bucket_date"],
                open=_num(row["open"]),
                high=_num(row["high"]),
                low=_num(row["low"]),
                close=_num(row["close"]),
                volume=int(row["volume"]) if row["volume"] is not None else None,
                amount=_num(row["amount"]),
            )
            for row in reversed(agg_rows)
        ]

    return IndexKlineResponse(
        code=code, name=kline_codes[code], period=period, bars=bars
    )


async def _index_daily_series(
    session: AsyncSession, code: str, end_date: date
) -> list[dict[str, Any]]:
    """单指数日线序列（本地 ``quote_kline_stock_daily`` 取 end_date 前最近一段）。"""
    bars = await fetch_daily_bars(
        session, code, end_date=end_date, limit=_TREND_DAYS + 1
    )
    return [
        {"date": bar.trade_date.isoformat(), "close": float(bar.close)}
        for bar in reversed(bars)
        if bar.close is not None
    ]


async def _historical_index_quotes(
    session: AsyncSession, trade_date: date
) -> list[IndexQuoteResponse]:
    """历史交易日的指数收盘行情；当日非交易日时返回空列表。"""
    target = trade_date.isoformat()
    all_series = await asyncio.gather(
        *(_index_daily_series(session, code, trade_date) for code in INDEX_CODES)
    )
    quotes: list[IndexQuoteResponse] = []
    for (code, name), series in zip(INDEX_CODES.items(), all_series, strict=True):
        idx = next(
            (i for i, bar in enumerate(series) if bar["date"] == target), None
        )
        if idx is None or idx == 0:
            continue
        close = series[idx]["close"]
        prev_close = series[idx - 1]["close"]
        change = round(close - prev_close, 3)
        quotes.append(
            IndexQuoteResponse(
                code=code,
                name=name,
                price=close,
                change=change,
                change_pct=round(change / prev_close * 100, 2) if prev_close else 0.0,
                amount=None,
                trend=[
                    bar["close"] for bar in series[max(0, idx - _TREND_DAYS + 1) : idx + 1]
                ],
            )
        )
    return quotes
