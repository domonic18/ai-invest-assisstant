"""个股 K 线业务服务。"""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.kline import KlineDaily
from app.repositories.market.kline_repository import (
    PERIOD_BUCKET,
    fetch_aggregated_bars,
    fetch_daily_bars,
    list_daily_paginated,
)
from app.services.market.stock_service import get_stock_by_code


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

    return {
        "code": stock_code,
        "name": stock.stock_name or stock_code,
        "period": period,
        "bars": bars,
    }
