"""板块异动检测服务：四维规则判定（涨跌幅/量能/齐动性/趋势拐点）+ 强度评分 + 幂等落库。

检测数据源以板块收盘快照 ``quote_sector_daily`` 为基础，但检测池收敛到
同花顺指数同名覆盖的板块（一级行业 + 概念，见 ``kline_repository.
list_ths_sector_names``），保证榜单上每个板块的详情页都有真实指数 K 线；
趋势维由 THS 板块日 K 经 ``trend_facts`` 计算拐点（量能确认），板块缺 K 线
时该维跳过不抛错。规则确定性可单测。归因字段由 anomaly-attribution skill
异步回填，本服务不触碰（docs/arch/08-anomaly-analysis.md §2/§4/§7）。
"""

from dataclasses import asdict, dataclass
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kline import SectorKlineDaily
from app.models.market_anomaly import SectorAnomaly
from app.repositories.market import (
    anomaly_repository,
    kline_repository,
    sector_quote_repository,
)
from app.schemas.anomaly import SectorAnomalyItem, SectorAnomalyResponse
from app.services.market.anomaly_common import (
    CATEGORY_RESONANCE,
    CATEGORY_ROTATION,
    SECTOR_DIM_PRICE,
    SECTOR_DIM_SYNC,
    SECTOR_DIM_TREND,
    SECTOR_DIM_VOLUME,
    AnomalyInputNotReadyError,
)
from app.services.market.trend_facts import Bar, compute_trend_facts

logger = structlog.get_logger(__name__)

# 强度赋分：齐动性 > 涨跌幅 > 趋势拐点 > 量能，多维度齐中 +10（四维齐中 110 封顶 100）
_SCORE_SYNC = 35
_SCORE_PRICE = 25
_SCORE_VOLUME = 15
_SCORE_TREND = 25
_SCORE_MULTI_DIM_BONUS = 10


@dataclass(frozen=True)
class SectorDetectionParams:
    """检测阈值，任务 config_params 的默认值来源（调参不改代码）。"""

    price_move_pct: float = 2.0
    volume_ratio: float = 2.0
    sync_ratio: float = 0.8
    baseline_days: int = 5
    attribution_top_n: int = 10


DEFAULT_SECTOR_PARAMS = SectorDetectionParams()


def evaluate_sector(
    *,
    change_pct: float | None,
    amount_ratio: float | None,
    up_count: int | None,
    down_count: int | None,
    trend_hit: bool = False,
    params: SectorDetectionParams = DEFAULT_SECTOR_PARAMS,
) -> tuple[list[str], int, str]:
    """单板块四维判定（价格/量能/齐动/趋势拐点），返回（命中维度, 强度 0-100, 分类）。

    分类二分：多维度齐中为趋势共振，单维度命中为轮动补涨。
    量能基线不足时 amount_ratio 为 None，该维度跳过、其余维度正常判定；
    板块 K 线缺失时 trend_hit=False（趋势维跳过，不作为异常抛出）。
    """
    dims: list[str] = []
    score = 0
    if change_pct is not None and abs(change_pct) >= params.price_move_pct:
        dims.append(SECTOR_DIM_PRICE)
        score += _SCORE_PRICE
    if amount_ratio is not None and amount_ratio >= params.volume_ratio:
        dims.append(SECTOR_DIM_VOLUME)
        score += _SCORE_VOLUME
    if (
        up_count is not None
        and down_count is not None
        and up_count + down_count > 0
        and up_count / (up_count + down_count) >= params.sync_ratio
    ):
        dims.append(SECTOR_DIM_SYNC)
        score += _SCORE_SYNC
    if trend_hit:
        dims.append(SECTOR_DIM_TREND)
        score += _SCORE_TREND
    if len(dims) >= 2:
        score += _SCORE_MULTI_DIM_BONUS
    category = CATEGORY_RESONANCE if len(dims) >= 2 else CATEGORY_ROTATION
    return dims, min(score, 100), category


def _sector_bars(rows: list[SectorKlineDaily]) -> list[Bar]:
    """板块指数 ORM 行转 trend_facts 升序 bar（剔除收盘缺失的行）。"""
    return [
        {
            "trade_date": row.trade_date,
            "open": float(row.open) if row.open is not None else None,
            "high": float(row.high) if row.high is not None else None,
            "low": float(row.low) if row.low is not None else None,
            "close": float(row.close),
            "volume": int(row.volume) if row.volume is not None else None,
        }
        for row in rows
        if row.close is not None
    ]


async def run_sector_detection(
    session: AsyncSession,
    trade_date: date,
    params: SectorDetectionParams = DEFAULT_SECTOR_PARAMS,
) -> list[SectorAnomaly]:
    """扫描指定交易日的板块快照（仅 THS 指数同名覆盖池）并落库，返回异动行（强度降序）。

    快照缺失或 THS 指数宇宙为空（板块指数采集未完成）抛
    :class:`AnomalyInputNotReadyError`，由定时任务退避重试；
    幂等：按 (trade_date, sector_type, sector_code) 覆盖检测字段，
    同日重跑时清理已收敛出池的残留异动行（归因字段仅池内保留）。
    """
    snapshots = await sector_quote_repository.list_all_by_date(session, trade_date)
    if not snapshots:
        raise AnomalyInputNotReadyError

    ths_universe = set(await kline_repository.list_ths_sector_names(session))
    if not ths_universe:
        raise AnomalyInputNotReadyError
    snapshots = [
        snap
        for snap in snapshots
        if (snap.sector_type, snap.sector_name) in ths_universe
    ]

    # 量能基线与趋势事实均取 THS 板块日 K（检测池本就按 THS 同名收敛，名称键
    # 天然匹配；快照表上线晚无历史积累，K 线表自带约一年历史）。17:30 板块日 K
    # 采集完成后 17:45 检测可取到当日 bar；板块缺 K 线时趋势维跳过不抛错。
    bars_by_key = await kline_repository.map_sector_kline_by_name(
        session, sorted({snap.sector_name for snap in snapshots})
    )
    baselines = await kline_repository.avg_amount_by_sector_name(
        session, before=trade_date, limit_days=params.baseline_days
    )
    baseline_ready = bool(baselines)

    rows: list[dict] = []
    for snap in snapshots:
        change_pct = float(snap.change_pct) if snap.change_pct is not None else None
        amount = float(snap.amount) if snap.amount is not None else None
        amount_ratio: float | None = None
        baseline = baselines.get((snap.sector_type, snap.sector_name))
        if baseline is not None and amount is not None:
            avg_amount, days = baseline
            if days >= params.baseline_days and avg_amount > 0:
                amount_ratio = round(amount / avg_amount, 2)
        sector_bars = _sector_bars(
            bars_by_key.get((snap.sector_type, snap.sector_name), [])
        )
        facts = compute_trend_facts(sector_bars)
        trend_hit = bool(facts.turning_points)
        dims, strength, category = evaluate_sector(
            change_pct=change_pct,
            amount_ratio=amount_ratio,
            up_count=snap.up_count,
            down_count=snap.down_count,
            trend_hit=trend_hit,
            params=params,
        )
        if not dims:
            continue
        rows.append(
            {
                "sector_type": snap.sector_type,
                "sector_code": snap.sector_code,
                "sector_name": snap.sector_name,
                "change_pct": change_pct,
                "amount": amount,
                "amount_ratio": amount_ratio,
                "up_count": snap.up_count,
                "down_count": snap.down_count,
                "trend_facts": asdict(facts) if sector_bars else None,
                "anomaly_types": dims,
                "strength": strength,
                "attribution_category": category,
            }
        )

    rows.sort(key=lambda item: item["strength"], reverse=True)
    removed = await anomaly_repository.delete_sector_rows_outside_pool(
        session, trade_date, {(s.sector_type, s.sector_code) for s in snapshots}
    )
    persisted = await anomaly_repository.upsert_sector_rows(session, trade_date, rows)
    await session.commit()
    logger.info(
        "sector_anomaly_detection_done",
        trade_date=trade_date.isoformat(),
        scanned=len(snapshots),
        detected=len(rows),
        pool_stale_removed=removed,
        baseline_ready=baseline_ready,
    )
    return persisted


async def get_sector_anomaly_board(
    session: AsyncSession,
    trade_date: date | None = None,
    sector_type: str | None = None,
) -> SectorAnomalyResponse | None:
    """板块异动榜（强度降序）；未指定日期时取最新检测日，无数据返回 None。"""
    target = trade_date or await anomaly_repository.latest_sector_trade_date(session)
    if target is None:
        return None
    rows = await anomaly_repository.list_sector_anomalies(session, target, sector_type)
    return SectorAnomalyResponse(
        trade_date=target,
        total=len(rows),
        items=[
            SectorAnomalyItem(
                sector_type=row.sector_type,
                sector_code=row.sector_code,
                sector_name=row.sector_name,
                change_pct=float(row.change_pct) if row.change_pct is not None else None,
                amount=float(row.amount) if row.amount is not None else None,
                amount_ratio=(
                    float(row.amount_ratio) if row.amount_ratio is not None else None
                ),
                up_count=row.up_count,
                down_count=row.down_count,
                anomaly_types=list(row.anomaly_types or []),
                strength=row.strength,
                attribution_category=row.attribution_category,
                attribution_summary=row.attribution_summary,
            )
            for row in rows
        ],
    )


async def list_sector_anomaly_trade_dates(session: AsyncSession) -> list[date]:
    """有板块异动检测数据的交易日（升序），日历打点用。"""
    return await anomaly_repository.list_sector_trade_dates(session)
