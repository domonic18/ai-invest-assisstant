"""Market overview (每日复盘) business services.

请求路径零直取数据源，全部由采集任务预先写入：
- 实时态：指数快照由 sina_index_spot 任务每分钟写 Redis（market:index_spot）；
- 日内时序：指数分钟线由 sina_index_minute 任务写 kline_minute 超表；
- 日频事实：涨跌统计/炸板数写 market_breadth、官方成交额写 market_amount、
  涨停池写 limit_up_pool、板块资金写 sector_fund_flow、日 K 写 kline_daily。
"""

import asyncio
import json
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from redis.asyncio import from_url
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import INDEX_CODES, KLINE_CHART_EXTRA_CODES
from app.models.kline import KlineDaily
from app.models.limit_up_pool import LimitUpPool
from app.models.market_amount import MarketAmount
from app.models.market_breadth import MarketBreadth
from app.models.sector_fund_flow import SectorFundFlow
from app.models.watchlist import UserWatchlist
from app.repositories.kline_repository import (
    PERIOD_BUCKET,
    fetch_aggregated_bars,
    fetch_daily_bars,
    fetch_max_daily_date,
    fetch_minute_bars,
    has_daily_bar,
    latest_minute_day,
    prev_minute_close,
)
from app.schemas.market import (
    CollectTaskResult,
    IndexIntradayPoint,
    IndexIntradayResponse,
    IndexKlineBar,
    IndexKlineResponse,
    IndexQuoteResponse,
    LeadingSectorItem,
    LimitUpGroup,
    LimitUpItem,
    LimitUpResponse,
    MarketStatsResponse,
    SectorFlowItem,
    SectorHeatItem,
    SectorOverviewResponse,
    WatchlistQuoteItem,
)

_INDEX_SPOT_KEY = "market:index_spot"
_TREND_DAYS = 30
_CN_TZ = ZoneInfo("Asia/Shanghai")


_redis_client: Any = None


def _redis() -> Any:
    """进程级共享 Redis 客户端（连接池复用，避免每次读写都新建连接）。"""
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(str(get_settings().redis_url))
    return _redis_client


async def _index_spot() -> list[dict[str, Any]] | None:
    """采集器写入的指数实时快照；采集器尚未覆盖时为 None。"""
    raw = await _redis().get(_INDEX_SPOT_KEY)
    return json.loads(raw) if raw else None


async def get_index_intraday(
    session: AsyncSession, code: str, trade_date: date | None = None
) -> IndexIntradayResponse:
    """指数分时图数据（价格 + 量能），只读 kline_minute（采集器每分钟写入）。

    默认取表内最近交易日；指定历史日期时取当日分钟序列，无数据抛
    ValueError（分钟线自采集上线起累积，更早日期不存在）。
    昨收优先取前一交易日分钟尾 bar，缺失时回退日 K 收盘。
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


async def _local_index_closes(
    session: AsyncSession, code: str, end_date: date | None, limit: int
) -> list[float]:
    """本地 kline_daily 最近 limit 根收盘（升序）；无数据返回空。"""
    bars = await fetch_daily_bars(session, code, end_date=end_date, limit=limit)
    return [float(bar.close) for bar in reversed(bars) if bar.close is not None]


async def _db_index_spot(session: AsyncSession) -> list[dict[str, Any]]:
    """实时快照缺失时的降级：由 kline_daily 最近两根日 K 合成行情快照。"""
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


async def get_index_quotes(
    session: AsyncSession,
    trade_date: date | None = None,
) -> list[IndexQuoteResponse]:
    """四大指数行情（含近 30 日收盘趋势）。

    默认取采集器写入 Redis 的实时快照（缺失时由日 K 合成）；
    指定历史交易日时从本地 kline_daily 取当日收盘与涨跌。
    趋势与日 K 均只读本地库，请求路径不触达数据源。
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


async def _index_daily_series(
    session: AsyncSession, code: str, end_date: date
) -> list[dict[str, Any]]:
    """单指数日线序列（本地 kline_daily 取 end_date 前最近一段）。"""
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


def _num(value: Any) -> float | None:
    return float(value) if value is not None else None


async def get_index_kline(
    session: AsyncSession,
    code: str,
    period: str = "daily",
    limit: int = 250,
) -> IndexKlineResponse:
    """指数多周期 K 线（升序返回）。

    daily 直读本地 kline_daily；weekly/monthly/quarterly/yearly 由
    TimescaleDB time_bucket 聚合，聚合周期的 date 取周期首根交易日。
    标的范围：四大指数（INDEX_CODES）+ K 线图扩展标的（KLINE_CHART_EXTRA_CODES，
    沪深300ETF/富时A50）。
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
    """当日涨跌统计：取 market_breadth 不晚于 resolved 的最新一行（采集器写入）。

    盘前/周末时最新一行是上一交易日收盘快照，与实时快照口径一致；
    采集器尚未覆盖时返回空统计（前端展示 "-"），不在请求路径抓取数据源。
    涨停数在东财涨停池入库后覆盖为池计数（盘中为快照估算）；跌停数同理，
    由 limit-down-pool 盘后任务把官方池家数写回 market_breadth。
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

    优先取 market_breadth 当日行（采集器收盘后写入，含涨跌家数）；
    该表未覆盖的更早日期回退旧口径：涨停数取数据库涨停池（与涨停梯队
    口径一致），跌停/上涨/下跌/平盘家数返回 None/0。
    涨停数一律以东财涨停池计数为准（官方池口径，不含 ST）；跌停数取
    行内 limit_down_count（limit-down-pool 盘后写入官方池家数）。
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
    """官方成交额（含前一有数据交易日），只读 market_amount 表。"""
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


async def get_market_stats(
    session: AsyncSession, trade_date: date | None = None
) -> MarketStatsResponse:
    """涨跌家数、成交额（含环比）与情绪温度。

    全部读库：涨跌统计取 market_breadth（采集器交易时段每 5 分钟写入），
    成交额取 market_amount（交易所官方盘后发布，盘中用指数快照成交额估算）。
    """
    latest_date = await resolve_latest_trade_date(session)
    resolved = trade_date or latest_date
    is_live = resolved >= latest_date

    if is_live:
        breadth = await _live_breadth(session, resolved)
    else:
        breadth = await _historical_breadth(session, resolved)

    amount, prev_amount = await _amount_pair(session, resolved)
    if amount is None and is_live:
        # 交易所官方数据盘后发布，盘中回退到指数快照成交额估算
        spot = await _index_spot()
        if spot is None:
            spot = await _db_index_spot(session)
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


_INDEX_BENCHMARK = "sh000001"


async def resolve_latest_trade_date(session: AsyncSession) -> date:
    """最近交易日：以指数日 K 为权威。

    盘中日 K 未出时，若当日已有涨跌统计（采集器盘中写入）则取当日；
    否则回退到最近一根指数日 K 的日期。避免被涨停池等
    可能被非交易日污染表的 max(trade_date) 带偏。
    """
    today = date.today()
    kline_max = await fetch_max_daily_date(session, _INDEX_BENCHMARK)
    if kline_max is None:
        return today
    if today > kline_max and today.weekday() < 5:
        has_breadth = await session.scalar(
            select(func.count())
            .select_from(MarketBreadth)
            .where(MarketBreadth.trade_date == today)
        )
        if has_breadth:
            return today
    return kline_max


async def is_trading_day(session: AsyncSession, day: date) -> bool:
    """以指数日 K 为准判断交易日；日 K 未覆盖的近期工作日按交易日放行。"""
    if day.weekday() >= 5:
        return False
    kline_max = await fetch_max_daily_date(session, _INDEX_BENCHMARK)
    if kline_max is None or day > kline_max:
        return True
    return await has_daily_bar(session, _INDEX_BENCHMARK, day)


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

    continuous_rate = (
        round(continuous / total, 4)
        if total and continuous is not None
        else None
    )

    # 炸板家数由 eastmoney_broken_pool 任务盘后写入 market_breadth
    broken_count = await session.scalar(
        select(MarketBreadth.broken_count).where(
            MarketBreadth.trade_date == trade_date
        )
    )

    broken_rate = (
        round(broken_count / (total + broken_count), 4)
        if broken_count is not None and total + broken_count > 0
        else None
    )
    return continuous_rate, broken_rate, broken_count


_SEAL_OPEN_THRESHOLD = "093000"  # 开盘（含集合竞价）即封板的时间上界
_INDUSTRY_SUFFIXES = ("Ⅲ", "Ⅱ")


def _seal_type(first_seal_time: str | None, break_count: int | None) -> str | None:
    """开盘涨停形态推导：一字板=开盘封板全天未开；T字板=开盘封板盘中打开后回封。

    first_seal_time 为 "092500" 式 6 位零填充字符串，同长度数字串可直接按字典序比较。
    """
    if first_seal_time is None or first_seal_time > _SEAL_OPEN_THRESHOLD:
        return None
    return "一字板" if not break_count else "T字板"


def _normalize_industry(name: str) -> str:
    """东财二级行业名去级次后缀（"白酒Ⅱ"→"白酒"），用于匹配板块资金流行业名。"""
    for suffix in _INDUSTRY_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _build_limit_up_groups(
    items: list[LimitUpItem], sector_rows: list[SectorFundFlow]
) -> list[LimitUpGroup]:
    """按行业分组涨停个股，组行情匹配板块资金流（精确→归一化→互相包含）。"""
    stats = {
        _normalize_industry(row.sector_name): (
            float(row.change_pct) if row.change_pct is not None else None,
            float(row.main_net_inflow)
            if row.main_net_inflow is not None
            else None,
        )
        for row in sector_rows
    }

    def _sector_stats(industry: str) -> tuple[float | None, float | None]:
        normalized = _normalize_industry(industry)
        if normalized in stats:
            return stats[normalized]
        for name, value in stats.items():
            if normalized in name or name in normalized:
                return value
        return None, None

    by_industry: dict[str, list[LimitUpItem]] = {}
    for item in items:
        by_industry.setdefault(item.industry or "其他", []).append(item)

    groups: list[LimitUpGroup] = []
    for industry, group_items in by_industry.items():
        group_items.sort(
            key=lambda item: (
                -(item.consecutive_boards or 0),
                item.first_seal_time or "999999",
            )
        )
        change_pct, inflow = _sector_stats(industry)
        groups.append(
            LimitUpGroup(
                industry=industry,
                count=len(group_items),
                change_pct=change_pct,
                main_net_inflow=inflow,
                items=group_items,
            )
        )
    groups.sort(
        key=lambda group: (
            group.industry == "其他",
            -group.count,
            -(group.change_pct if group.change_pct is not None else float("-inf")),
        )
    )
    return groups


def _limit_up_response(
    resolved: date,
    items: list[LimitUpItem],
    groups: list[LimitUpGroup] | None = None,
) -> LimitUpResponse:
    ladder = [item for item in items if (item.consecutive_boards or 0) >= 2]
    return LimitUpResponse(
        trade_date=resolved,
        total=len(items),
        first_board=len(items) - len(ladder),
        continuous=len(ladder),
        max_boards=max((item.consecutive_boards or 0) for item in items) if items else None,
        ladder=ladder,
        items=items,
        groups=groups or [],
    )


async def get_limit_up(
    session: AsyncSession, trade_date: date | None = None
) -> LimitUpResponse:
    """涨停板与连板天梯（只读 limit_up_pool）。

    默认取最近交易日：盘中未收盘时当日涨停池尚未写入，返回空（前端
    提示未收盘），不回退展示前一交易日的旧数据；周末/节假日解析到
    最近一根指数日 K 的日期，展示该日收盘池。
    """
    resolved = trade_date or await resolve_latest_trade_date(session)

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
        return _limit_up_response(resolved, [])

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
            seal_type=_seal_type(row.first_seal_time, row.break_count),
        )
        for row in rows
    ]
    sector_rows = list(
        (
            await session.execute(
                select(SectorFundFlow).where(
                    SectorFundFlow.sector_type == "industry",
                    SectorFundFlow.trade_date == resolved,
                )
            )
        )
        .scalars()
        .all()
    )
    groups = _build_limit_up_groups(items, sector_rows)
    return _limit_up_response(resolved, items, groups)


async def get_sector_overview(
    session: AsyncSession,
    trade_date: date | None = None,
    sector_type: str = "industry",
) -> SectorOverviewResponse:
    """板块热力图 + 资金净流入/流出 TOP5 + 领涨板块。

    默认取最近交易日（与涨停池同口径）：盘中未收盘时当日板块资金
    尚未写入，返回空（前端提示未收盘），不回退展示前一交易日的旧数据。
    """
    resolved = trade_date or await resolve_latest_trade_date(session)

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
    for item in watch_items:
        raw = await redis.get(f"quote:{item.stock_code}")
        if raw:
            quotes[item.stock_code] = json.loads(raw)

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


_BACKFILL_TASKS = (
    "limit-up-pool",
    "broken-pool",
    "limit-down-pool",
    "market-amount",
    "sector-fund-flow",
)


class NonTradingDayError(ValueError):
    """指定日期不是交易日。"""


async def backfill_trade_date(
    session: AsyncSession, trade_date: date
) -> list[CollectTaskResult]:
    """补采指定交易日的行情数据（涨停池/炸板池/跌停池/成交额/板块资金流）。

    任务经队列异步执行（板块资金流受东财限流约束约需 10 分钟），
    返回各任务的派发结果；涨跌家数（market_breadth）为盘中快照，
    数据源无历史，无法补采。
    """
    if not await is_trading_day(session, trade_date):
        raise NonTradingDayError(
            f"{trade_date.isoformat()} 不是交易日，无法补采数据"
        )

    from collector.runtime.dispatcher import dispatch_collector_task

    results: list[CollectTaskResult] = []
    for task in _BACKFILL_TASKS:
        await dispatch_collector_task(
            session, task, {"trade_date": trade_date.isoformat()}
        )
        results.append(
            CollectTaskResult(task=task, status="dispatched", items_collected=0)
        )
    return results
