"""个股异动检测服务：两段式管线（全市场快照初筛 + 候选日 K 精算）。

初筛用新浪全市场快照（涨跌幅 / 换手率），精算逐候选拉新浪日 K，按温程趋势
理论三类拐点（突破/风险/支撑，量能确认）+ 量比 / 换手 / 涨幅判定。K 线获取经
``fetch_kline`` 注入（collector 层负责 IO），规则内核纯函数可离线单测
（docs/arch/06-anomaly-analysis.md §3/§4）。趋势事实由 ``trend_facts`` 计算，
与复盘技术面文本同源。
"""

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_anomaly import StockAnomaly
from app.repositories.market import anomaly_repository, sector_quote_repository
from app.repositories.market.stock_concept_repository import StockConceptRepository
from app.repositories.user.watchlist_repository import WatchlistRepository
from app.schemas.anomaly import (
    AnomalySectorRef,
    StockAnomalyItem,
    StockAnomalyResponse,
)
from app.services.market.anomaly_common import (
    CATEGORY_ACCELERATION,
    CATEGORY_BREAKDOWN,
    CATEGORY_BREAKOUT,
    CATEGORY_PULLBACK,
    STOCK_DIM_BREAKOUT,
    STOCK_DIM_PRICE,
    STOCK_DIM_RISK_BREAK,
    STOCK_DIM_SUPPORT_TEST,
    STOCK_DIM_TURNOVER,
    STOCK_DIM_VOLUME,
    AnomalyInputNotReadyError,
)
from app.services.market.trend_facts import (
    CHANNEL_UP,
    TURNING_BREAKOUT,
    TURNING_RISK_BREAK,
    TURNING_SUPPORT_TEST,
    compute_trend_facts,
)

logger = structlog.get_logger(__name__)

# MA60 计算（温程趋势体系：M60 生命线为趋势分界）
MA60_WINDOW = 60
# 精算所需最少 K 线根数：60 根均线 + 1 根昨日对照
MIN_BARS_FOR_MA60 = MA60_WINDOW + 1
# 量比基线：5 日均量（不含当日）
VOLUME_BASELINE_DAYS = 5
MIN_BARS_FOR_VOLUME_RATIO = VOLUME_BASELINE_DAYS + 1

# 强度赋分（温程趋势理论）：突破拐点 > 风险拐点 > 量比 > 支撑拐点 > 换手 > 涨幅；
# 上升通道 +5，下跌反抽 ×0.7。拐点维由 trend_facts 量能确认判定。
_SCORE_BREAKOUT = 40
_SCORE_RISK_BREAK = 30
_SCORE_VOLUME = 25
_SCORE_SUPPORT_TEST = 25
_SCORE_TURNOVER = 20
_SCORE_PRICE = 15
_SCORE_TREND_BONUS = 5
_PULLBACK_FACTOR = 0.7

# 异动条目展示的所属板块上限（按当日涨跌幅绝对值取最相关的前几个）
SECTOR_REFS_CAP = 3


@dataclass(frozen=True)
class StockDetectionParams:
    """初筛与精算阈值，任务 config_params 的默认值来源（调参不改代码）。"""

    screen_change_pct: float = 6.0
    screen_turnover_pct: float = 8.0
    screen_candidate_cap: int = 250
    price_move_pct: float = 6.0
    volume_ratio: float = 2.5
    turnover_pct: float = 8.0
    breakout_volume_ratio: float = 2.0
    attribution_top_n: int = 20


DEFAULT_STOCK_PARAMS = StockDetectionParams()


def pre_screen_spot(
    spot_rows: list[dict],
    params: StockDetectionParams = DEFAULT_STOCK_PARAMS,
) -> list[dict]:
    """全市场快照初筛：涨跌幅或换手率任一触发即入围。

    按预分（2×|涨跌幅| + 换手率）降序截断候选，控制日 K 拉取量。
    """
    candidates = [
        row
        for row in spot_rows
        if (row.get("change_pct") is not None and abs(row["change_pct"]) >= params.screen_change_pct)
        or (row.get("turnover_rate") is not None and row["turnover_rate"] >= params.screen_turnover_pct)
    ]
    candidates.sort(
        key=lambda row: 2 * abs(row.get("change_pct") or 0.0)
        + (row.get("turnover_rate") or 0.0),
        reverse=True,
    )
    return candidates[: params.screen_candidate_cap]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def evaluate_stock(
    bars: list[dict],
    spot: dict,
    params: StockDetectionParams = DEFAULT_STOCK_PARAMS,
) -> dict | None:
    """候选精算：温程趋势拐点（量能确认）+ 量价维度判定。

    Args:
        bars: 日 K（升序），字段 date/open/high/low/close/volume/turnover。
        spot: 快照行，字段 stock_code/stock_name/close/change_pct/turnover_rate。
        params: 检测阈值。

    Returns:
        命中任一维度时返回落库字段 dict（含分类与 trend_facts），未命中返回
        None。K 线不足 61 根时 MA60/拐点不可判定（趋势维不命中，量价维照常）；
        周线 M60 之下突破拐点不成立（trend_facts 带周线位置，次新股不门控），
        存量 wire 字段 ma60/is_above_ma60/ma60_breakout 仍按旧口径写入。
    """
    usable = [bar for bar in bars if bar.get("close") is not None]
    if len(usable) < 2:
        return None
    today = usable[-1]
    close = float(today["close"])
    prev_close = float(usable[-2]["close"])

    volume_ratio: float | None = None
    if len(usable) >= MIN_BARS_FOR_VOLUME_RATIO:
        baseline_vols = [
            float(bar["volume"]) for bar in usable[-6:-1] if bar.get("volume") is not None
        ]
        if len(baseline_vols) == 5:
            baseline = _mean(baseline_vols)
            if baseline > 0 and today.get("volume") is not None:
                volume_ratio = round(float(today["volume"]) / baseline, 2)

    facts = compute_trend_facts(usable)
    turning = facts.turning_points

    # 存量 wire 字段（前端兼容展示），不再参与计分
    ma60: float | None = None
    is_above_ma60 = False
    ma60_breakout = False
    if len(usable) >= MIN_BARS_FOR_MA60 and facts.ma60 is not None:
        ma60 = round(facts.ma60, 4)
        closes = [float(bar["close"]) for bar in usable]
        prev_ma60 = _mean(closes[-(MA60_WINDOW + 1) : -1])
        is_above_ma60 = close > ma60
        ma60_breakout = (
            is_above_ma60
            and prev_close <= prev_ma60
            and volume_ratio is not None
            and volume_ratio >= params.breakout_volume_ratio
        )

    change_pct = spot.get("change_pct")
    turnover_rate = spot.get("turnover_rate")
    if turnover_rate is None and today.get("turnover") is not None:
        turnover_rate = float(today["turnover"])

    dims: list[str] = []
    score: float = 0
    if TURNING_BREAKOUT in turning:
        dims.append(STOCK_DIM_BREAKOUT)
        score += _SCORE_BREAKOUT
    if TURNING_RISK_BREAK in turning:
        dims.append(STOCK_DIM_RISK_BREAK)
        score += _SCORE_RISK_BREAK
    if TURNING_SUPPORT_TEST in turning:
        dims.append(STOCK_DIM_SUPPORT_TEST)
        score += _SCORE_SUPPORT_TEST
    if volume_ratio is not None and volume_ratio >= params.volume_ratio:
        dims.append(STOCK_DIM_VOLUME)
        score += _SCORE_VOLUME
    if turnover_rate is not None and turnover_rate >= params.turnover_pct:
        dims.append(STOCK_DIM_TURNOVER)
        score += _SCORE_TURNOVER
    if change_pct is not None and abs(change_pct) >= params.price_move_pct:
        dims.append(STOCK_DIM_PRICE)
        score += _SCORE_PRICE
    if not dims:
        return None

    up_day = (change_pct or 0.0) > 0
    if TURNING_BREAKOUT in turning:
        category = CATEGORY_BREAKOUT
    elif TURNING_RISK_BREAK in turning:
        # 风险拐点是独立强信号，不按反抽打折
        category = CATEGORY_BREAKDOWN
    elif ma60 is None:
        # MA60 不可判定：正向变动按趋势内加速，负向按下跌反抽弱信号
        category = CATEGORY_ACCELERATION if up_day else CATEGORY_PULLBACK
    elif is_above_ma60 and up_day:
        category = CATEGORY_ACCELERATION
    else:
        category = CATEGORY_PULLBACK

    if category == CATEGORY_PULLBACK:
        score *= _PULLBACK_FACTOR
    elif facts.channel == CHANNEL_UP:
        score += _SCORE_TREND_BONUS

    return {
        "stock_code": spot["stock_code"],
        "stock_name": spot.get("stock_name") or "",
        "close": round(close, 4),
        "change_pct": change_pct,
        "turnover_rate": round(turnover_rate, 4) if turnover_rate is not None else None,
        "volume_ratio": volume_ratio,
        "ma60": ma60,
        "is_above_ma60": is_above_ma60,
        "ma60_breakout": ma60_breakout,
        "trend_facts": asdict(facts),
        "anomaly_types": dims,
        "strength": max(0, min(round(score), 100)),
        "attribution_category": category,
    }


async def run_stock_detection(
    session: AsyncSession,
    trade_date: date,
    spot_rows: list[dict],
    fetch_kline: Callable[[str], Awaitable[list[dict] | None]],
    params: StockDetectionParams = DEFAULT_STOCK_PARAMS,
) -> list[StockAnomaly]:
    """两段式检测：快照初筛 → 候选日 K 精算 → 幂等落库。

    Args:
        session: 数据库会话（服务层拥有事务边界）。
        trade_date: 交易日。
        spot_rows: 全市场快照行（collector 层拉取）。
        fetch_kline: 逐候选拉日 K 的注入函数（升序 bars，异常/缺失返回 None）。
        params: 检测阈值。

    Returns:
        落库后的异动行（强度降序）。快照为空抛
        :class:`AnomalyInputNotReadyError` 由定时任务退避重试。
    """
    if not spot_rows:
        raise AnomalyInputNotReadyError

    candidates = pre_screen_spot(spot_rows, params)
    rows: list[dict] = []
    for candidate in candidates:
        # 拉取 K 线用新浪标识（bj/sh/sz 前缀只在快照里有），回退 6 位代码
        bars = await fetch_kline(candidate.get("sina_symbol") or candidate["stock_code"])
        if not bars:
            continue
        evaluated = evaluate_stock(bars, candidate, params)
        if evaluated is not None:
            rows.append(evaluated)

    rows.sort(key=lambda item: item["strength"], reverse=True)
    persisted = await anomaly_repository.upsert_stock_rows(session, trade_date, rows)
    await session.commit()
    logger.info(
        "stock_anomaly_detection_done",
        trade_date=trade_date.isoformat(),
        spot_rows=len(spot_rows),
        candidates=len(candidates),
        detected=len(rows),
    )
    return persisted


async def get_stock_anomaly_board(
    session: AsyncSession,
    trade_date: date | None = None,
    user_id: int | None = None,
) -> StockAnomalyResponse | None:
    """个股异动榜（强度降序）；未指定日期时取最新检测日，无数据返回 None。

    ``user_id`` 提供时对命中自选股的条目做关联标注（is_watchlist）。
    """
    target = trade_date or await anomaly_repository.latest_stock_trade_date(session)
    if target is None:
        return None
    rows = await anomaly_repository.list_stock_anomalies(session, target)
    watchlist_codes: set[str] = set()
    if user_id is not None and rows:
        watchlist_codes = set(
            await WatchlistRepository(session).map_by_user_and_codes(
                user_id, [row.stock_code for row in rows]
            )
        )
    sector_refs = await _build_sector_refs(session, rows, target)
    return StockAnomalyResponse(
        trade_date=target,
        total=len(rows),
        items=[
            StockAnomalyItem(
                stock_code=row.stock_code,
                stock_name=row.stock_name,
                close=float(row.close) if row.close is not None else None,
                change_pct=float(row.change_pct) if row.change_pct is not None else None,
                turnover_rate=(
                    float(row.turnover_rate) if row.turnover_rate is not None else None
                ),
                volume_ratio=(
                    float(row.volume_ratio) if row.volume_ratio is not None else None
                ),
                ma60=float(row.ma60) if row.ma60 is not None else None,
                is_above_ma60=row.is_above_ma60,
                ma60_breakout=row.ma60_breakout,
                anomaly_types=list(row.anomaly_types or []),
                sectors=sector_refs.get(row.stock_code, []),
                strength=row.strength,
                attribution_category=row.attribution_category,
                attribution_summary=row.attribution_summary,
                is_watchlist=row.stock_code in watchlist_codes,
            )
            for row in rows
        ],
    )


async def _build_sector_refs(
    session: AsyncSession,
    rows: list[StockAnomaly],
    trade_date: date,
) -> dict[str, list[AnomalySectorRef]]:
    """各异动股的所属板块引用（概念映射 × 当日板块涨幅），按 |涨幅| 取前 N。"""
    if not rows:
        return {}
    concepts = await StockConceptRepository(session).get_concepts_by_stocks(
        [row.stock_code for row in rows]
    )
    if not concepts:
        return {}
    pct_by_name = {
        sector.sector_name: float(sector.change_pct)
        for sector in await sector_quote_repository.list_all_by_date(session, trade_date)
        if sector.change_pct is not None
    }
    refs: dict[str, list[AnomalySectorRef]] = {}
    for stock_code, names in concepts.items():
        candidates = [
            AnomalySectorRef(name=name, change_pct=pct_by_name.get(name)) for name in names
        ]
        candidates.sort(
            key=lambda ref: (
                abs(ref.change_pct) if ref.change_pct is not None else -1.0
            ),
            reverse=True,
        )
        refs[stock_code] = candidates[:SECTOR_REFS_CAP]
    return refs


async def list_stock_anomaly_trade_dates(session: AsyncSession) -> list[date]:
    """有个股异动检测数据的交易日（升序），日历打点用。"""
    return await anomaly_repository.list_stock_trade_dates(session)
