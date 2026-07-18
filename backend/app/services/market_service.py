"""Market overview (每日复盘) business services.

External quote data (index spots, market breadth) is fetched via akshare in
worker threads and cached in Redis; historical data (涨停池 / 板块资金) is read
from PostgreSQL populated by collector tasks.
"""

import asyncio
import json
from datetime import date, timedelta
from typing import Any, cast

from redis.asyncio import from_url
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.kline import KlineDaily
from app.models.limit_up_pool import LimitUpPool
from app.models.sector_fund_flow import SectorFundFlow
from app.models.watchlist import UserWatchlist
from app.schemas.market import (
    IndexIntradayPoint,
    IndexIntradayResponse,
    IndexQuoteResponse,
    LeadingSectorItem,
    LimitUpItem,
    LimitUpResponse,
    MarketStatsResponse,
    SectorFlowItem,
    SectorHeatItem,
    SectorOverviewResponse,
    WatchlistQuoteItem,
)

INDEX_CODES: dict[str, str] = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
}

_INDEX_CACHE_KEY = "market:indices"
_INDEX_CACHE_TTL = 60
_TREND_CACHE_KEY = "market:index_trend:{code}"
_TREND_CACHE_TTL = 6 * 3600
_TREND_DAYS = 30
_BREADTH_CACHE_KEY = "market:breadth"
_BREADTH_CACHE_TTL = 300
_HIST_BREADTH_CACHE_KEY = "market:breadth:{date}"
_INDEX_DAILY_CACHE_KEY = "market:index_daily:{code}"
_INDEX_DAILY_CACHE_TTL = 6 * 3600
_BROKEN_CACHE_KEY = "market:broken_pool"
_BROKEN_CACHE_TTL = 300
_ZT_POOL_CACHE_KEY = "market:zt_pool:{date}"
_INTRADAY_CACHE_KEY = "market:index_intraday:{code}"
_INTRADAY_CACHE_TTL = 60
_HIST_CACHE_TTL = 24 * 3600
_AMOUNT_CACHE_KEY = "market:amount_pair:{date}"
_AMOUNT_CACHE_TTL = 6 * 3600


def _redis() -> Any:
    return from_url(str(get_settings().redis_url))


async def _cache_get(key: str) -> Any:
    redis = _redis()
    try:
        raw = await redis.get(key)
        return json.loads(raw) if raw else None
    finally:
        await redis.close()


async def _cache_set(key: str, value: Any, ttl: int) -> None:
    redis = _redis()
    try:
        await redis.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
    finally:
        await redis.close()


def _fetch_index_spot() -> list[dict[str, Any]]:
    import akshare as ak  # type: ignore[import-untyped]

    df = ak.stock_zh_index_spot_sina()
    rows: list[dict[str, Any]] = []
    for code, name in INDEX_CODES.items():
        matched = df[df["代码"] == code]
        if matched.empty:
            continue
        row = matched.iloc[0]
        rows.append(
            {
                "code": code,
                "name": name,
                "price": float(row["最新价"]),
                "change": float(row["涨跌额"]),
                "change_pct": float(row["涨跌幅"]),
                "amount": float(row["成交额"]),
            }
        )
    return rows


def _fetch_index_trend(code: str) -> list[float]:
    import akshare as ak  # type: ignore[import-untyped]

    df = ak.stock_zh_index_daily(symbol=code)
    closes = df["close"].tail(_TREND_DAYS).tolist()
    return [float(value) for value in closes]


def _limit_threshold(code: str, name: str) -> float:
    """各板块涨跌幅限制阈值（含 0.5pp 容差）。"""
    if code.startswith("bj"):
        return 29.5
    if code.startswith(("sz30", "sh68")):
        return 19.5
    if "ST" in name:
        return 4.8
    return 9.5


def _count_breadth(df: Any) -> dict[str, Any]:
    """从全市场行情快照统计涨跌家数与涨跌停数（口径与同花顺一致）。

    涨跌停判定：涨跌幅达到板块阈值且收盘封板（最新价=最高/最低价），含 ST。
    """
    import pandas as pd  # type: ignore[import-untyped]

    df = df.dropna(subset=["涨跌幅"])
    up = int((df["涨跌幅"] > 0).sum())
    down = int((df["涨跌幅"] < 0).sum())
    flat = int((df["涨跌幅"] == 0).sum())

    thresholds = pd.Series(
        [
            _limit_threshold(str(code), str(name))
            for code, name in zip(df["代码"], df["名称"], strict=True)
        ],
        index=df.index,
    )
    sealed_up = (df["涨跌幅"] >= thresholds) & (
        (df["最新价"] - df["最高"]).abs() < 1e-6
    )
    sealed_down = (df["涨跌幅"] <= -thresholds) & (
        (df["最新价"] - df["最低"]).abs() < 1e-6
    )

    stat_time = ""
    if "时间戳" in df.columns and len(df):
        stat_time = str(df["时间戳"].iloc[0])

    return {
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "limit_up_count": int(sealed_up.sum()),
        "limit_down_count": int(sealed_down.sum()),
        "stat_time": stat_time,
    }


def _fetch_market_breadth() -> dict[str, Any]:
    import contextlib
    import io

    import akshare as ak  # type: ignore[import-untyped]

    # akshare 抓取全市场行情约 20s 且打印进度条，抑制输出保持日志干净
    with contextlib.redirect_stdout(io.StringIO()):
        df = ak.stock_zh_a_spot()
    return _count_breadth(df)


def _fetch_broken_pool_count(trade_date: date) -> int:
    import akshare as ak  # type: ignore[import-untyped]

    df = ak.stock_zt_pool_zbgc_em(date=trade_date.strftime("%Y%m%d"))
    return 0 if df is None else len(df)


def _fetch_limit_down_count(trade_date: date) -> int:
    """东财跌停池（支持历史日期），非交易日或无数据时返回 0。"""
    import akshare as ak  # type: ignore[import-untyped]

    try:
        df = ak.stock_zt_pool_dtgc_em(date=trade_date.strftime("%Y%m%d"))
    except Exception:  # noqa: BLE001
        return 0
    return 0 if df is None else len(df)


def _fetch_zt_pool_items(trade_date: date) -> list[dict[str, Any]]:
    """东财涨停池（支持历史日期），字段与 LimitUpItem 对齐。"""
    import akshare as ak  # type: ignore[import-untyped]

    try:
        df = ak.stock_zt_pool_em(date=trade_date.strftime("%Y%m%d"))
    except Exception:  # noqa: BLE001
        return []
    if df is None or df.empty:
        return []
    return [
        {
            "stock_code": str(row["代码"]),
            "stock_name": str(row["名称"]),
            "change_pct": float(row["涨跌幅"]),
            "latest_price": float(row["最新价"]),
            "sealed_amount": float(row["封板资金"]),
            "first_seal_time": str(row["首次封板时间"]),
            "last_seal_time": str(row["最后封板时间"]),
            "break_count": int(row["炸板次数"]),
            "limit_stat": str(row["涨停统计"]),
            "consecutive_boards": int(row["连板数"]),
            "industry": str(row["所属行业"]),
        }
        for _, row in df.iterrows()
    ]


async def _zt_pool_items(trade_date: date) -> list[dict[str, Any]]:
    """东财涨停池（Redis 缓存：历史 24h，当日 300s）。"""
    cache_key = _ZT_POOL_CACHE_KEY.format(date=trade_date.isoformat())
    cached = await _cache_get(cache_key)
    if cached is not None:
        return cast(list[dict[str, Any]], cached)
    items = await asyncio.to_thread(_fetch_zt_pool_items, trade_date)
    ttl = _HIST_CACHE_TTL if trade_date < date.today() else _BROKEN_CACHE_TTL
    await _cache_set(cache_key, items, ttl)
    return items


def _fetch_index_daily(code: str) -> list[dict[str, Any]]:
    """新浪指数日线全历史（date/close），用于历史日期复盘。"""
    import akshare as ak  # type: ignore[import-untyped]

    df = ak.stock_zh_index_daily(symbol=code)
    if df is None or df.empty:
        return []
    return [
        {"date": str(row["date"])[:10], "close": float(row["close"])}
        for _, row in df.iterrows()
    ]


def _fetch_index_intraday(code: str, trade_date: date | None) -> dict[str, Any]:
    """新浪分钟级指数行情（约最近 8 个交易日），截取目标交易日。

    返回目标日分钟点、目标日前一交易日收盘（取自分钟序列，可能为 None）。
    """
    import akshare as ak  # type: ignore[import-untyped]

    df = ak.stock_zh_a_minute(symbol=code, period="1", adjust="")
    if df is None or df.empty:
        return {"trade_date": None, "points": [], "prev_close": None}
    dates = df["day"].str.slice(0, 10)
    target = trade_date.isoformat() if trade_date else str(dates.max())
    day_df = df[dates == target]
    points = [
        {
            "time": str(row["day"])[11:16],
            "price": float(row["close"]),
            "volume": float(row["volume"]),
            "amount": float(row["amount"]),
        }
        for _, row in day_df.iterrows()
    ]
    prev_close: float | None = None
    earlier = sorted(d for d in dates.unique() if d < target)
    if earlier:
        prev_close = float(df[dates == earlier[-1]].iloc[-1]["close"])
    return {"trade_date": target, "points": points, "prev_close": prev_close}


def _fetch_official_amount(day: date) -> float | None:
    """交易所官方两市成交额（元）。非交易日或数据未发布时返回 None。"""
    import akshare as ak  # type: ignore[import-untyped]

    try:
        sse = ak.stock_sse_deal_daily(date=day.strftime("%Y%m%d"))
        szse = ak.stock_szse_summary(date=day.strftime("%Y%m%d"))
        sse_amount = float(sse.loc[sse["单日情况"] == "成交金额", "股票"].iloc[0])
        szse_amount = float(szse.loc[szse["证券类别"] == "股票", "成交金额"].iloc[0])
    except Exception:  # noqa: BLE001
        return None
    return sse_amount * 1e8 + szse_amount


def _fetch_amount_pair(trade_date: date) -> dict[str, float | None]:
    """指定交易日与前一交易日的两市成交额（元）。"""
    amount = _fetch_official_amount(trade_date)
    prev_amount: float | None = None
    day = trade_date - timedelta(days=1)
    for _ in range(7):
        prev_amount = _fetch_official_amount(day)
        if prev_amount is not None:
            break
        day -= timedelta(days=1)
    return {"amount": amount, "prev_amount": prev_amount}


async def get_index_intraday(
    code: str, trade_date: date | None = None
) -> IndexIntradayResponse:
    """指数分时图数据（价格 + 量能）。

    最新交易日缓存 60s；历史日期（数据不可变）缓存 24h。
    新浪分钟序列仅覆盖约 8 个交易日，超出范围的历史日期抛出 ValueError。
    """
    if code not in INDEX_CODES:
        raise ValueError(f"不支持的指数代码: {code}")

    cache_key = (
        _INTRADAY_CACHE_KEY.format(code=code)
        if trade_date is None
        else f"market:index_intraday:{code}:{trade_date.isoformat()}"
    )
    cached = await _cache_get(cache_key)
    if cached:
        return IndexIntradayResponse(**cached)

    intraday = await asyncio.to_thread(_fetch_index_intraday, code, trade_date)
    points = [IndexIntradayPoint(**item) for item in intraday["points"]]
    if trade_date is not None and not points:
        raise ValueError(
            f"{trade_date.isoformat()} 无分时数据（仅支持最近约 8 个交易日）"
        )

    prev_close = intraday["prev_close"]
    if trade_date is None:
        # 最新交易日用实时快照计算昨收（更精确），分钟序列昨收作兜底
        spot = await _cache_get(_INDEX_CACHE_KEY)
        if spot is None:
            spot = await asyncio.to_thread(_fetch_index_spot)
            await _cache_set(_INDEX_CACHE_KEY, spot, _INDEX_CACHE_TTL)
        matched = next((item for item in spot if item["code"] == code), None)
        if matched:
            prev_close = round(matched["price"] - matched["change"], 3)
    if prev_close is None:
        prev_close = points[0].price if points else 0.0

    resolved_date = (
        date.fromisoformat(intraday["trade_date"])
        if intraday["trade_date"]
        else date.today()
    )
    response = IndexIntradayResponse(
        code=code,
        name=INDEX_CODES[code],
        trade_date=resolved_date,
        prev_close=prev_close,
        points=points,
    )
    ttl = _INTRADAY_CACHE_TTL if trade_date is None else _HIST_CACHE_TTL
    await _cache_set(cache_key, response.model_dump(mode="json"), ttl)
    return response


async def get_index_quotes(
    trade_date: date | None = None,
) -> list[IndexQuoteResponse]:
    """四大指数行情（含近 30 日收盘趋势）。

    默认取实时快照（Redis 缓存 60s）；指定历史交易日时从新浪日线
    序列取当日收盘与涨跌（日线全历史缓存 6h）。
    """
    if trade_date is not None:
        quotes = await _historical_index_quotes(trade_date)
        if quotes or trade_date < date.today():
            return quotes
        # 当日盘中日线尚未更新，回退实时快照
    spot = await _cache_get(_INDEX_CACHE_KEY)
    if spot is None:
        spot = await asyncio.to_thread(_fetch_index_spot)
        await _cache_set(_INDEX_CACHE_KEY, spot, _INDEX_CACHE_TTL)

    quotes = []
    for item in spot:
        trend_key = _TREND_CACHE_KEY.format(code=item["code"])
        trend = await _cache_get(trend_key)
        if trend is None:
            try:
                trend = await asyncio.to_thread(_fetch_index_trend, item["code"])
                await _cache_set(trend_key, trend, _TREND_CACHE_TTL)
            except Exception:
                trend = []
        quotes.append(IndexQuoteResponse(**item, trend=trend or []))
    return quotes


async def _historical_index_quotes(trade_date: date) -> list[IndexQuoteResponse]:
    """历史交易日的指数收盘行情；当日非交易日时返回空列表。"""
    target = trade_date.isoformat()
    quotes: list[IndexQuoteResponse] = []
    for code, name in INDEX_CODES.items():
        daily_key = _INDEX_DAILY_CACHE_KEY.format(code=code)
        series = await _cache_get(daily_key)
        if series is None:
            series = await asyncio.to_thread(_fetch_index_daily, code)
            await _cache_set(daily_key, series, _INDEX_DAILY_CACHE_TTL)
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
    返回 (score, 涨停比)。
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


async def _historical_breadth(
    session: AsyncSession, trade_date: date
) -> dict[str, Any]:
    """历史交易日的涨跌统计。

    涨停数取数据库涨停池（与涨停梯队口径一致），跌停数取东财跌停池；
    上涨/下跌/平盘家数无免费历史数据源，返回 None（前端展示为 "-"）。
    结果按日期缓存 24h（历史数据不可变）。
    """
    cache_key = _HIST_BREADTH_CACHE_KEY.format(date=trade_date.isoformat())
    cached = await _cache_get(cache_key)
    if cached is not None:
        return cast(dict[str, Any], cached)

    limit_up = await session.scalar(
        select(func.count())
        .select_from(LimitUpPool)
        .where(LimitUpPool.trade_date == trade_date)
    ) or 0
    if not limit_up:
        limit_up = len(await _zt_pool_items(trade_date))
    limit_down = await asyncio.to_thread(_fetch_limit_down_count, trade_date)
    breadth: dict[str, Any] = {
        "up_count": None,
        "down_count": None,
        "flat_count": None,
        "limit_up_count": limit_up or 0,
        "limit_down_count": limit_down,
    }
    await _cache_set(cache_key, breadth, _HIST_CACHE_TTL)
    return breadth


async def get_market_stats(
    session: AsyncSession, trade_date: date | None = None
) -> MarketStatsResponse:
    """涨跌家数、成交额（含环比）与情绪温度。

    默认（或指定日期不早于最近数据日）取实时全市场快照；指定更早的
    历史交易日时，涨跌停数取数据库/东财历史池，上涨/下跌家数与情绪
    温度无历史数据源，返回 None。
    """
    latest_date = await _latest_limit_up_date(session) or date.today()
    resolved = trade_date or latest_date
    is_live = resolved >= latest_date

    if is_live:
        breadth = await _cache_get(_BREADTH_CACHE_KEY)
        if breadth is None:
            breadth = await asyncio.to_thread(_fetch_market_breadth)
            await _cache_set(_BREADTH_CACHE_KEY, breadth, _BREADTH_CACHE_TTL)
    else:
        breadth = await _historical_breadth(session, resolved)

    amount_key = _AMOUNT_CACHE_KEY.format(date=resolved.isoformat())
    amount_pair = await _cache_get(amount_key)
    if amount_pair is None:
        amount_pair = await asyncio.to_thread(_fetch_amount_pair, resolved)
        await _cache_set(amount_key, amount_pair, _AMOUNT_CACHE_TTL)

    amount = amount_pair.get("amount")
    prev_amount = amount_pair.get("prev_amount")
    if amount is None and is_live:
        # 交易所官方数据尚未发布时（盘中）回退到实时行情估算
        indices = await get_index_quotes()
        amount = sum(
            (quote.amount or 0)
            for quote in indices
            if quote.code in ("sh000001", "sz399001")
        ) or None

    amount_change = None
    amount_change_pct = None
    if amount is not None and prev_amount:
        amount_change = round(amount - prev_amount, 2)
        amount_change_pct = round((amount - prev_amount) / prev_amount * 100, 2)

    continuous_rate, broken_rate, broken_count = await _limit_up_rates(
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
        broken_count=broken_count,
        emotion_score=score,
        emotion_label=_emotion_label(score) if score is not None else None,
        limit_up_ratio=limit_up_ratio,
        continuous_rate=continuous_rate,
        broken_rate=broken_rate,
    )


async def _latest_limit_up_date(session: AsyncSession) -> date | None:
    return await session.scalar(select(func.max(LimitUpPool.trade_date)))


async def _limit_up_rates(
    session: AsyncSession, trade_date: date
) -> tuple[float | None, float | None, int | None]:
    """连板率 / 炸板率 / 炸板家数。

    连板率 = 连板(≥2板)家数 / 涨停总家数；炸板率 = 炸板家数 / (涨停 + 炸板)。
    数据库无当日涨停池时回退到东财历史涨停池。
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
    else:
        pool = await _zt_pool_items(trade_date)
        if pool:
            total = len(pool)
            continuous = sum(
                1 for item in pool if (item["consecutive_boards"] or 0) >= 2
            )

    continuous_rate = (
        round(continuous / total, 4)
        if total and continuous is not None
        else None
    )

    cache_key = f"{_BROKEN_CACHE_KEY}:{trade_date.isoformat()}"
    broken_count = await _cache_get(cache_key)
    if broken_count is None:
        try:
            broken_count = await asyncio.to_thread(
                _fetch_broken_pool_count, trade_date
            )
            await _cache_set(cache_key, broken_count, _BROKEN_CACHE_TTL)
        except Exception:
            broken_count = None

    broken_rate = (
        round(broken_count / (total + broken_count), 4)
        if broken_count is not None and total + broken_count > 0
        else None
    )
    return continuous_rate, broken_rate, broken_count


def _limit_up_response(resolved: date, items: list[LimitUpItem]) -> LimitUpResponse:
    ladder = [item for item in items if (item.consecutive_boards or 0) >= 2]
    return LimitUpResponse(
        trade_date=resolved,
        total=len(items),
        first_board=len(items) - len(ladder),
        continuous=len(ladder),
        max_boards=max((item.consecutive_boards or 0) for item in items) if items else None,
        ladder=ladder,
        items=items,
    )


async def get_limit_up(
    session: AsyncSession, trade_date: date | None = None
) -> LimitUpResponse:
    """涨停板与连板天梯，默认取最近一个有数据的交易日。

    数据库无当日数据时（历史日期）回退到东财历史涨停池。
    """
    resolved = trade_date or await _latest_limit_up_date(session)
    if resolved is None:
        return LimitUpResponse(trade_date=date.today())

    stmt = (
        select(LimitUpPool)
        .where(LimitUpPool.trade_date == resolved)
        .order_by(
            LimitUpPool.consecutive_boards.desc().nullslast(),
            LimitUpPool.sealed_amount.desc().nullslast(),
        )
    )
    rows = list((await session.execute(stmt)).scalars().all())

    if not rows:
        pool_items = [
            LimitUpItem(**item) for item in await _zt_pool_items(resolved)
        ]
        pool_items.sort(
            key=lambda item: (
                -(item.consecutive_boards or 0),
                -(item.sealed_amount or 0),
            )
        )
        return _limit_up_response(resolved, pool_items)

    items = [
        LimitUpItem(
            stock_code=row.stock_code,
            stock_name=row.stock_name,
            change_pct=float(row.change_pct) if row.change_pct is not None else None,
            latest_price=(
                float(row.latest_price) if row.latest_price is not None else None
            ),
            sealed_amount=(
                float(row.sealed_amount) if row.sealed_amount is not None else None
            ),
            first_seal_time=row.first_seal_time,
            last_seal_time=row.last_seal_time,
            break_count=row.break_count,
            limit_stat=row.limit_stat,
            consecutive_boards=row.consecutive_boards,
            industry=row.industry,
        )
        for row in rows
    ]
    return _limit_up_response(resolved, items)


async def get_sector_overview(
    session: AsyncSession,
    trade_date: date | None = None,
    sector_type: str = "industry",
) -> SectorOverviewResponse:
    """板块热力图 + 资金净流入/流出 TOP5 + 领涨板块。"""
    resolved = trade_date or await session.scalar(
        select(func.max(SectorFundFlow.trade_date)).where(
            SectorFundFlow.sector_type == sector_type
        )
    )
    if resolved is None:
        return SectorOverviewResponse(trade_date=date.today())

    stmt = select(SectorFundFlow).where(
        SectorFundFlow.sector_type == sector_type,
        SectorFundFlow.trade_date == resolved,
    )
    rows = list((await session.execute(stmt)).scalars().all())

    def _pct(row: SectorFundFlow) -> float:
        return float(row.change_pct) if row.change_pct is not None else 0.0

    def _inflow(row: SectorFundFlow) -> float:
        return float(row.main_net_inflow) if row.main_net_inflow is not None else 0.0

    by_pct_desc = sorted(rows, key=_pct, reverse=True)
    heat_rows = by_pct_desc[:10] + by_pct_desc[-5:]
    heatmap = [
        SectorHeatItem(
            sector_name=row.sector_name,
            change_pct=float(row.change_pct) if row.change_pct is not None else None,
        )
        for row in heat_rows
    ]

    by_inflow = sorted(rows, key=_inflow, reverse=True)
    top_inflow = [
        SectorFlowItem(
            sector_name=row.sector_name,
            main_net_inflow=_inflow(row),
            top_stock_name=row.top_stock_name,
        )
        for row in by_inflow[:5]
        if _inflow(row) > 0
    ]
    top_outflow = [
        SectorFlowItem(
            sector_name=row.sector_name,
            main_net_inflow=_inflow(row),
            top_stock_name=row.top_stock_name,
        )
        for row in reversed(by_inflow[-5:])
        if _inflow(row) < 0
    ]

    limit_up = await get_limit_up(session, resolved)
    industry_limit_count: dict[str, int] = {}
    industry_stocks: dict[str, list[str]] = {}
    for item in limit_up.items:
        if not item.industry:
            continue
        industry_limit_count[item.industry] = (
            industry_limit_count.get(item.industry, 0) + 1
        )
        industry_stocks.setdefault(item.industry, [])
        if item.stock_name and len(industry_stocks[item.industry]) < 2:
            industry_stocks[item.industry].append(item.stock_name)

    leading = [
        LeadingSectorItem(
            sector_name=row.sector_name,
            change_pct=float(row.change_pct) if row.change_pct is not None else None,
            limit_up_count=industry_limit_count.get(row.sector_name, 0),
            main_net_inflow=_inflow(row),
            top_stock_names=(
                industry_stocks.get(row.sector_name)
                or ([row.top_stock_name] if row.top_stock_name else [])
            ),
        )
        for row in by_pct_desc[:5]
    ]

    return SectorOverviewResponse(
        trade_date=resolved,
        heatmap=heatmap,
        top_inflow=top_inflow,
        top_outflow=top_outflow,
        leading=leading,
    )


async def get_watchlist_quotes(
    session: AsyncSession, user_id: int
) -> list[WatchlistQuoteItem]:
    """自选股实时行情：优先 Redis 快照，缺失时回退最近 K 线收盘价。"""
    stmt = (
        select(UserWatchlist)
        .where(UserWatchlist.user_id == user_id)
        .order_by(UserWatchlist.created_at.desc())
    )
    watch_items = list((await session.execute(stmt)).scalars().all())
    if not watch_items:
        return []

    redis = _redis()
    quotes: dict[str, dict[str, Any]] = {}
    try:
        for item in watch_items:
            raw = await redis.get(f"quote:{item.stock_code}")
            if raw:
                quotes[item.stock_code] = json.loads(raw)
    finally:
        await redis.close()

    results: list[WatchlistQuoteItem] = []
    for item in watch_items:
        cached = quotes.get(item.stock_code)
        if cached:
            results.append(
                WatchlistQuoteItem(
                    code=item.stock_code,
                    name=cached.get("stock_name"),
                    price=cached.get("price"),
                    change_pct=cached.get("pct_change"),
                    amount=cached.get("amount"),
                    tags=list(item.tags or []),
                    updated_at=cached.get("updated_at"),
                )
            )
            continue

        kline = (
            await session.execute(
                select(KlineDaily)
                .where(KlineDaily.stock_code == item.stock_code)
                .order_by(KlineDaily.trade_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        results.append(
            WatchlistQuoteItem(
                code=item.stock_code,
                price=float(kline.close) if kline and kline.close is not None else None,
                change_pct=(
                    float(kline.pct_change)
                    if kline and kline.pct_change is not None
                    else None
                ),
                amount=(
                    float(kline.amount) if kline and kline.amount is not None else None
                ),
                tags=list(item.tags or []),
                updated_at=kline.trade_date.isoformat() if kline else None,
            )
        )
    return results
