"""指数行情：分时 / 实时快照 / 多周期 K 线。

请求路径零直取数据源：
- 实时态：指数快照由 ``sina_index_spot`` 任务每分钟写 Redis（``market:index_spot``）；
- 日内时序：指数分钟线由 ``sina_index_minute`` 任务写 ``quote_kline_stock_minute`` 超表；
- 日频事实：日 K 写 ``quote_kline_stock_daily``，多周期由 TimescaleDB ``time_bucket`` 聚合。
"""

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get
from app.core.clock import CN_TZ, today_cn
from app.core.constants import (
    INDEX_CODES,
    INDEX_TREND_DAYS,
    KLINE_CHART_EXTRA_CODES,
    TURNOVER_COMPARE_CODES,
)
from app.repositories.market.kline_repository import (
    PERIOD_BUCKET,
    fetch_aggregated_bars,
    fetch_daily_bars,
    fetch_minute_bars,
    fetch_minute_bars_multi,
    latest_minute_day,
    prev_minute_close,
    prev_minute_day,
)
from app.schemas.market import (
    IndexIntradayPoint,
    IndexIntradayResponse,
    IndexKlineBar,
    IndexKlineResponse,
    IndexQuoteResponse,
    TurnoverComparePoint,
    TurnoverCompareResponse,
)

_INDEX_SPOT_KEY = "market:index_spot"
_TREND_DAYS = INDEX_TREND_DAYS


async def _index_spot() -> list[dict[str, Any]] | None:
    """采集器写入的指数实时快照；采集器尚未覆盖时为 None。"""
    raw = await cache_get(_INDEX_SPOT_KEY)
    return json.loads(raw) if raw else None


async def _local_index_closes(
    session: AsyncSession, code: str, end_date: date | None, limit: int
) -> list[float]:
    """本地 ``quote_kline_stock_daily`` 最近 limit 根收盘（升序）；无数据返回空。"""
    bars = await fetch_daily_bars(session, code, end_date=end_date, limit=limit)
    return [float(bar.close) for bar in reversed(bars) if bar.close is not None]


async def _bar_synthesized_spot(
    session: AsyncSession, codes: dict[str, str]
) -> list[dict[str, Any]]:
    """实时快照缺失时的降级：由 ``quote_kline_stock_daily`` 最近两根日 K 合成行情快照。"""
    quotes: list[dict[str, Any]] = []
    for code, name in codes.items():
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


async def _kline_extra_quotes(session: AsyncSession) -> list[IndexQuoteResponse]:
    """K 线扩展标的（沪深300ETF/富时A50）行情：无分钟/快照通道，按最近日 K 合成。"""
    spot = await _bar_synthesized_spot(session, KLINE_CHART_EXTRA_CODES)
    trends = [
        await _local_index_closes(session, item["code"], None, _TREND_DAYS)
        for item in spot
    ]
    return [
        IndexQuoteResponse(**item, trend=trend)
        for item, trend in zip(spot, trends, strict=True)
    ]


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
            code=code, name=INDEX_CODES[code], trade_date=today_cn(),
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
            time=bar.trade_time.astimezone(CN_TZ).strftime("%H:%M"),
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


def _cum_amount_yi(bars: list[Any]) -> dict[str, float]:
    """分钟 bar 序列（可含多标的）-> {HH:MM: 累计成交额（亿元）}。

    amount 为该分钟成交额（元），None 按 0；同一时刻多标的相加。
    """
    per_minute: dict[str, float] = {}
    for bar in bars:
        hhmm = bar.trade_time.astimezone(CN_TZ).strftime("%H:%M")
        per_minute[hhmm] = per_minute.get(hhmm, 0.0) + float(bar.amount or 0.0)
    cumulative: dict[str, float] = {}
    running = 0.0
    for hhmm in sorted(per_minute):
        running += per_minute[hhmm]
        cumulative[hhmm] = running
    return cumulative


def build_turnover_points(
    today_bars: list[Any], prev_bars: list[Any]
) -> tuple[list[TurnoverComparePoint], float]:
    """两市分钟 bar -> （逐分钟累计对比点，昨日全天累计）。

    单位亿元。``today``/``prev`` 为 TURNOVER_COMPARE_CODES 合计口径；
    昨日基线按时刻对齐、当日时刻在昨日无 bar 时沿用此前累计（前向填充）。
    """
    today_cum = _cum_amount_yi(today_bars)
    prev_cum = _cum_amount_yi(prev_bars)
    points: list[TurnoverComparePoint] = []
    running_prev = 0.0
    for hhmm in sorted(today_cum):
        if hhmm in prev_cum:
            running_prev = prev_cum[hhmm]
        today = round(today_cum[hhmm] / 1e8, 1)
        prev = round(running_prev / 1e8, 1)
        # 完全无昨日基线时 diff 置 0：全量差额会误读为「大幅放量」
        diff = round(today - prev, 1) if prev_cum else 0.0
        points.append(
            TurnoverComparePoint(time=hhmm, today=today, prev=prev, diff=diff)
        )
    # 昨日全天累计取昨日序列自身最后一格（盘中时前向填充值只到当前时刻，
    # 不是全天值；HH:MM 字典序即时序）
    prev_full_yi = round(prev_cum[max(prev_cum)] / 1e8, 1) if prev_cum else 0.0
    return points, prev_full_yi


async def get_turnover_compare(
    session: AsyncSession, trade_date: date | None = None
) -> TurnoverCompareResponse:
    """两市量能对比（诊大盘）：当日 vs 昨日同期累计成交额 + 全天预测。

    数据只读 ``quote_kline_stock_minute``（上证指数 + 深证综指合计，与交易所
    官方总额误差 <0.1%）。预测 = 昨日全天 × 当日/昨日同期累计比（同一 U 型
    节奏基线下的外推），收盘后自然收敛为实际总额；无昨日基线时为 None。
    目标日无分钟数据时返回空 points（前端展示空态，不抛错）。
    """
    target = trade_date or await latest_minute_day(session, "sh000001")
    if target is None:
        return TurnoverCompareResponse(trade_date=today_cn())
    prev_day = await prev_minute_day(session, "sh000001", target)
    codes = list(TURNOVER_COMPARE_CODES)
    today_bars = await fetch_minute_bars_multi(session, codes, target)
    prev_bars = (
        await fetch_minute_bars_multi(session, codes, prev_day) if prev_day else []
    )
    points, prev_full_yi = build_turnover_points(today_bars, prev_bars)

    last = points[-1] if points else None
    forecast = (
        round(prev_full_yi * last.today / last.prev, 1)
        if last and last.prev > 0 and prev_full_yi > 0
        else None
    )
    return TurnoverCompareResponse(
        trade_date=target,
        prev_trade_date=prev_day,
        today_amount=last.today if last else None,
        prev_amount=prev_full_yi or None,
        forecast_amount=forecast,
        points=points,
    )


async def get_index_quotes(
    session: AsyncSession,
    trade_date: date | None = None,
) -> list[IndexQuoteResponse]:
    """四大指数 + K 线扩展标的行情（含近 30 日收盘趋势）。

    默认取采集器写入 Redis 的实时快照（缺失时由日 K 合成）；
    扩展标的（沪深300ETF/富时A50）无实时通道，恒由日 K 合成；
    指定历史交易日时从本地 ``quote_kline_stock_daily`` 取当日收盘与涨跌；
    指定当日时日 K 缺当日 bar（新浪收盘日 K 约 18:00 后才陆续可用），
    由实时快照补齐缺失指数（收盘后快照即当日收盘价）。
    """
    if trade_date is not None:
        quotes = await _historical_index_quotes(session, trade_date)
        if trade_date < today_cn():
            return quotes
        quotes = await _fill_today_from_spot(session, quotes, trade_date)
        if quotes:
            return quotes
        # 当日盘中日线尚未更新，回退实时快照
    spot = await _index_spot()
    if spot is None:
        spot = await _bar_synthesized_spot(session, INDEX_CODES)

    trends = [
        await _local_index_closes(session, item["code"], None, _TREND_DAYS)
        for item in spot
    ]
    quotes = [
        IndexQuoteResponse(**item, trend=trend)
        for item, trend in zip(spot, trends, strict=True)
    ]
    quotes.extend(await _kline_extra_quotes(session))
    return quotes


def _num(value: Any) -> float | None:
    return float(value) if value is not None else None


def _parse_spot_updated_at(raw: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


async def _fill_today_from_spot(
    session: AsyncSession,
    quotes: list[IndexQuoteResponse],
    trade_date: date,
) -> list[IndexQuoteResponse]:
    """当日日 K 缺失的指数用实时快照补齐（收盘后快照即当日收盘价）。

    仅采信 ``updated_at`` 落在交易日的快照条目，避免过期快照把旧收盘
    冒充当日行情；日 K 已命中的标的保持原样（保留日 K 口径的成交额）。
    扩展标的（无实时通道）与缺失且快照不可用的标的保持缺席，由上层
    如实披露。
    """
    spot = await _index_spot()
    if spot is None:
        return quotes
    covered = {quote.code for quote in quotes}
    filled = list(quotes)
    for item in spot:
        code = item.get("code")
        if code not in INDEX_CODES or code in covered:
            continue
        updated_at = _parse_spot_updated_at(item.get("updated_at"))
        if updated_at is None or updated_at.astimezone(CN_TZ).date() != trade_date:
            continue
        filled.append(
            IndexQuoteResponse(
                code=code,
                name=item.get("name") or INDEX_CODES[code],
                price=item["price"],
                change=item.get("change"),
                change_pct=item.get("change_pct"),
                amount=item.get("amount"),
                trend=await _local_index_closes(session, code, None, _TREND_DAYS),
            )
        )
    return filled


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
    kline_codes = {**INDEX_CODES, **KLINE_CHART_EXTRA_CODES}
    # 顺序查询：单个 AsyncSession 不允许并发操作，gather 会触发
    # "concurrent operations are not permitted" 直接崩掉取数工具
    all_series = [
        await _index_daily_series(session, code, trade_date) for code in kline_codes
    ]
    quotes: list[IndexQuoteResponse] = []
    for (code, name), series in zip(kline_codes.items(), all_series, strict=True):
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
