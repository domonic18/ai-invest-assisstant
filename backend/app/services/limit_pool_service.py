"""涨停板：池查询 + 题材分组 + 分时缩略图。

只读 ``pool_limit_up_stock`` + ``capital_fund_flow_sector`` + ``quote_kline_stock_minute``。
题材分组优先用 AI 归因（``limit_up_ai_service.get_cached_attribution``，只读缓存版）；
AI 未覆盖时回退按行业聚合 + 板块资金流匹配。
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capital_fund_flow_sector import SectorFundFlow
from app.models.pool_limit_up_stock import LimitUpPool
from app.repositories.market.kline_repository import fetch_minute_bars_multi
from app.schemas.market import (
    LimitUpGroup,
    LimitUpIntradayResponse,
    LimitUpItem,
    LimitUpResponse,
)
from app.services import limit_up_ai_service, trade_calendar_service
from app.services.limit_up_ai_service import LimitUpAttributionContent

_SEAL_OPEN_THRESHOLD = "093000"  # 开盘（含集合竞价）即封板的时间上界
_INDUSTRY_SUFFIXES = ("Ⅲ", "Ⅱ")
_INTRADAY_SAMPLE_POINTS = 60


def _seal_type(first_seal_time: str | None, broken_limit_count: int | None) -> str | None:
    """开盘涨停形态推导：一字板=开盘封板全天未开；T字板=开盘封板盘中打开后回封。

    first_seal_time 为 "092500" 式 6 位零填充字符串，同长度数字串可直接按字典序比较。
    """
    if first_seal_time is None or first_seal_time > _SEAL_OPEN_THRESHOLD:
        return None
    return "一字板" if not broken_limit_count else "T字板"


def _normalize_industry(name: str) -> str:
    """东财二级行业名去级次后缀（"白酒Ⅱ"→"白酒"），用于匹配板块资金流行业名。"""
    for suffix in _INDUSTRY_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _group_item_sort_key(item: LimitUpItem) -> tuple[int, str]:
    seal = item.last_seal_time or item.first_seal_time or "999999"
    return (-(item.consecutive_boards or 0), seal)


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
        group_items.sort(key=_group_item_sort_key)
        change_pct, inflow = _sector_stats(industry)
        groups.append(
            LimitUpGroup(
                name=industry,
                count=len(group_items),
                change_pct=change_pct,
                main_net_inflow=inflow,
                items=group_items,
            )
        )
    groups.sort(
        key=lambda group: (
            group.name == "其他",
            -group.count,
            -(group.change_pct if group.change_pct is not None else float("-inf")),
        )
    )
    return groups


def _build_ai_groups(
    items: list[LimitUpItem], attribution: LimitUpAttributionContent
) -> list[LimitUpGroup]:
    """按 AI 归因的题材分组（未覆盖个股归入最后的「其他」组）。"""
    by_code = {item.stock_code: item for item in items}
    assigned: set[str] = set()
    groups: list[LimitUpGroup] = []
    for group in attribution.groups:
        codes = [
            code
            for code in group.stock_codes
            if code in by_code and code not in assigned
        ]
        if not codes:
            continue
        assigned.update(codes)
        group_items = sorted((by_code[code] for code in codes), key=_group_item_sort_key)
        groups.append(
            LimitUpGroup(
                name=group.theme,
                count=len(group_items),
                reason=group.reason,
                items=group_items,
            )
        )
    rest = [item for item in items if item.stock_code not in assigned]
    if rest:
        rest.sort(key=_group_item_sort_key)
        groups.append(LimitUpGroup(name="其他", count=len(rest), items=rest))
    return groups


def _limit_up_response(
    resolved: date,
    items: list[LimitUpItem],
    groups: list[LimitUpGroup] | None = None,
    ai_generated: bool = False,
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
        ai_generated=ai_generated,
    )


async def get_limit_up(
    session: AsyncSession, trade_date: date | None = None
) -> LimitUpResponse:
    """涨停板与连板天梯（只读 ``pool_limit_up_stock``）。

    默认取最近交易日：盘中未收盘时当日涨停池尚未写入，返回空，
    不回退展示前一交易日的旧数据。
    """
    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(session)

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
            broken_limit_count=row.broken_limit_count,
            limit_status=row.limit_status,
            consecutive_boards=row.consecutive_boards,
            industry=row.industry,
            seal_type=_seal_type(row.first_seal_time, row.broken_limit_count),
        )
        for row in rows
    ]
    attribution = await limit_up_ai_service.get_cached_attribution(session, resolved)
    if attribution:
        for item in items:
            item.themes = attribution.stock_themes.get(item.stock_code, [])
        return _limit_up_response(
            resolved, items, _build_ai_groups(items, attribution), ai_generated=True
        )
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


def _downsample(values: list[float], limit: int = _INTRADAY_SAMPLE_POINTS) -> list[float]:
    """等距降采样（保留首尾点），供分时缩略图使用。"""
    if len(values) <= limit:
        return values
    step = (len(values) - 1) / (limit - 1)
    return [values[round(i * step)] for i in range(limit)]


async def get_limit_up_intraday(
    session: AsyncSession, trade_date: date | None = None
) -> LimitUpIntradayResponse:
    """涨停个股全天分时缩略图（每股 ≤60 个收盘价采样点，读 ``quote_kline_stock_minute``）。"""
    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(session)
    codes = list(
        (
            await session.execute(
                select(LimitUpPool.stock_code).where(
                    LimitUpPool.trade_date == resolved
                )
            )
        )
        .scalars()
        .all()
    )
    bars = await fetch_minute_bars_multi(session, codes, resolved)
    closes_by_code: dict[str, list[float]] = {}
    for bar in bars:
        if bar.close is None:
            continue
        closes_by_code.setdefault(bar.stock_code, []).append(float(bar.close))
    series = {
        code: _downsample(closes)
        for code, closes in closes_by_code.items()
        if closes
    }
    return LimitUpIntradayResponse(trade_date=resolved, series=series)
