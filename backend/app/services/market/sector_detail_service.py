"""板块详情聚合服务：真实板块指数 K 线（THS 桥接）+ 资金流 + 异动日标注。

K 线真相源为同花顺板块指数（按板块名与东财体系桥接）。检测池
（quote_sector_daily）含东财二/三级板块，同名覆盖率约 25%；无同名
THS 板块时返回 None（404），不做链式合成兜底。
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market import (
    anomaly_repository,
    kline_repository,
    sector_fund_flow_repository,
    sector_quote_repository,
)
from app.schemas.sector_detail import (
    SectorAnomalyDay,
    SectorDetailResponse,
    SectorFundFlowPoint,
    SectorKlineBar,
    SectorSnapshot,
)

_KLINE_BARS = 250
_FUND_FLOW_POINTS = 120
_ANOMALY_DAYS = 30


def _pct_from_closes(prev_close: float | None, close: float) -> float | None:
    """相邻收盘推算涨跌幅（首根无前收为 None）。"""
    if prev_close is None or prev_close == 0:
        return None
    return round((close / prev_close - 1) * 100, 4)


def _to_float(value: Decimal | float | None) -> float | None:
    """Decimal 数值转 float（None 透传），wire 层金额序列化约定。"""
    return float(value) if value is not None else None


async def get_sector_detail(
    session: AsyncSession, sector_type: str, sector_code: str
) -> SectorDetailResponse | None:
    """聚合板块详情；板块无同花顺同名指数时返回 None（404 语义）。"""
    quote_row = await sector_quote_repository.latest_sector_quote(
        session, sector_type, sector_code
    )
    sector_name = quote_row.sector_name if quote_row is not None else None
    if sector_name is None:
        flow_identity = await sector_fund_flow_repository.get_latest_by_code(
            session, sector_type, sector_code
        )
        sector_name = flow_identity.sector_name if flow_identity is not None else None
    if sector_name is None:
        return None

    ths_rows = await kline_repository.list_sector_kline_by_name(
        session, sector_name, limit=_KLINE_BARS
    )
    if not ths_rows:
        return None

    bars: list[SectorKlineBar] = []
    prev_close: float | None = None
    for row in ths_rows:
        close = float(row.close) if row.close is not None else 0.0
        bars.append(
            SectorKlineBar(
                trade_date=row.trade_date,
                open=float(row.open) if row.open is not None else None,
                high=float(row.high) if row.high is not None else None,
                low=float(row.low) if row.low is not None else None,
                close=close,
                volume=row.volume,
                amount=float(row.amount) if row.amount is not None else None,
                change_pct=_pct_from_closes(prev_close, close),
            )
        )
        prev_close = close

    flow_history = await sector_fund_flow_repository.list_history_by_code(
        session, sector_type, sector_code, limit=_FUND_FLOW_POINTS
    )
    anomaly_rows = await anomaly_repository.list_sector_anomalies_by_code(
        session, sector_type, sector_code, limit=_ANOMALY_DAYS
    )

    return SectorDetailResponse(
        sector_type=sector_type,
        sector_code=sector_code,
        sector_name=sector_name,
        bars=bars,
        fund_flow=[
            SectorFundFlowPoint(
                trade_date=row.trade_date,
                main_net_inflow=_to_float(row.main_net_inflow),
                super_large_net=_to_float(row.super_large_net),
                large_net=_to_float(row.large_net),
                medium_net=_to_float(row.medium_net),
                small_net=_to_float(row.small_net),
            )
            for row in flow_history
        ],
        anomaly_days=[
            SectorAnomalyDay(
                trade_date=row.trade_date,
                anomaly_types=list(row.anomaly_types or []),
                strength=row.strength,
                attribution_category=row.attribution_category,
                attribution_summary=row.attribution_summary,
            )
            for row in anomaly_rows
        ],
        snapshot=(
            SectorSnapshot(
                trade_date=quote_row.trade_date,
                close=float(quote_row.close) if quote_row.close is not None else None,
                change_pct=(
                    float(quote_row.change_pct)
                    if quote_row.change_pct is not None
                    else None
                ),
                amount=float(quote_row.amount) if quote_row.amount is not None else None,
                turnover_rate=(
                    float(quote_row.turnover_rate)
                    if quote_row.turnover_rate is not None
                    else None
                ),
                up_count=quote_row.up_count,
                down_count=quote_row.down_count,
                leader_stock_name=quote_row.leader_stock_name,
            )
            if quote_row is not None
            else None
        ),
    )
