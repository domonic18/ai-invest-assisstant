"""个股 K 线业务服务。"""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.kline import KlineDaily
from app.repositories.market.kline_repository import (
    PERIOD_BUCKET,
    count_daily_bars,
    fetch_aggregated_bars,
    fetch_daily_bars,
    list_daily_paginated,
)
from app.services.market import trade_calendar_service
from app.services.market.stock_service import get_stock_by_code

#: 健康历史的最少日 K 根数（约 3 个月交易日）——低于此值视为历史被截断
MIN_HEALTHY_BARS = 60
#: 上市满该自然日数才要求完整历史（次新股本身 bar 少属正常，不算截断）
_LISTED_DAYS_FOR_FULL_HISTORY = 120
#: 需要完整历史的 A 股市场（港股日 K 只保留近几日，ETF 无上市日，均不适用）
_FULL_HISTORY_MARKETS = frozenset({"sh", "sz", "bj"})


def is_history_truncated(
    *,
    market: str,
    listing_date: date | None,
    latest_trade_date: date,
    bar_count: int,
) -> bool:
    """库内日 K 历史是否被截断（不足以画出完整走势）。

    判据：已上市满 ``_LISTED_DAYS_FOR_FULL_HISTORY`` 自然日（次新股 bar 少
    属正常），但库内不足 ``MIN_HEALTHY_BARS`` 根——说明历史被中途截断
    （如锚点兜底只写末几根），需要补采全历史。

    Args:
        market: 股票市场（sh/sz/bj 为 A 股；hk 与 ETF 不适用本判据）。
        listing_date: 上市日期，缺失时不做判定（保守不触发补采）。
        latest_trade_date: 最近交易日。
        bar_count: 库内该股日 K 总根数。

    Returns:
        历史是否被截断。
    """
    if bar_count <= 0 or bar_count >= MIN_HEALTHY_BARS:
        return False
    if market not in _FULL_HISTORY_MARKETS or listing_date is None:
        return False
    return (latest_trade_date - listing_date).days > _LISTED_DAYS_FOR_FULL_HISTORY


def _to_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _to_int(value: Any) -> int | None:
    return int(value) if value is not None else None


async def get_kline_by_code(
    session: AsyncSession,
    stock_code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KlineDaily], int]:
    """分页查询日 K 线数据。"""
    return await list_daily_paginated(
        session,
        stock_code,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


async def get_stock_kline(
    session: AsyncSession,
    stock_code: str,
    period: str = "daily",
    limit: int = 250,
) -> dict[str, Any]:
    """获取个股多周期 K 线（升序返回）。"""
    stock = await get_stock_by_code(session, stock_code)
    if stock is None:
        raise BadRequestError(f"股票 {stock_code} 不存在")

    if period == "daily":
        rows = await fetch_daily_bars(session, stock_code, limit=limit)
        bars = [
            {
                "date": row.trade_date,
                "open": _to_float(row.open),
                "high": _to_float(row.high),
                "low": _to_float(row.low),
                "close": _to_float(row.close),
                "volume": _to_int(row.volume),
                "amount": _to_float(row.amount),
                "change_pct": _to_float(row.change_pct),
                "amplitude": _to_float(row.amplitude),
                "turnover_rate": _to_float(row.turnover_rate),
            }
            for row in reversed(rows)
        ]
    else:
        bucket = PERIOD_BUCKET.get(period)
        if bucket is None:
            raise BadRequestError(f"不支持的 K 线周期: {period}")
        agg_rows = await fetch_aggregated_bars(session, stock_code, bucket, limit=limit)
        bars = [
            {
                "date": row["bucket_date"],
                "open": _to_float(row["open"]),
                "high": _to_float(row["high"]),
                "low": _to_float(row["low"]),
                "close": _to_float(row["close"]),
                "volume": _to_int(row["volume"]),
                "amount": _to_float(row["amount"]),
            }
            for row in reversed(agg_rows)
        ]

    latest_trade_date = await trade_calendar_service.resolve_latest_trade_date(session)

    needs_backfill = False
    if period == "daily":
        bar_count = await count_daily_bars(session, stock_code)
        needs_backfill = is_history_truncated(
            market=stock.market,
            listing_date=stock.listing_date,
            latest_trade_date=latest_trade_date,
            bar_count=bar_count,
        )

    return {
        "code": stock_code,
        "name": stock.stock_name or stock_code,
        "period": period,
        "bars": bars,
        "latest_trade_date": latest_trade_date,
        "needs_backfill": needs_backfill,
        "min_healthy_bars": MIN_HEALTHY_BARS,
    }
