"""Stock intraday (minute) business services."""

from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market.kline_repository import (
    fetch_daily_bars,
    fetch_minute_bars,
    latest_minute_day,
    prev_minute_close,
)
from app.services.market.stock_service import get_stock_by_code

_CN_TZ = ZoneInfo("Asia/Shanghai")


def _to_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _to_int(value: Any) -> int | None:
    return int(value) if value is not None else None


async def get_stock_intraday(
    session: AsyncSession,
    stock_code: str,
    trade_date: date | None = None,
) -> dict[str, Any]:
    """获取个股分时数据（价格 + 成交量）。"""
    stock = await get_stock_by_code(session, stock_code)
    if stock is None:
        raise ValueError(f"股票 {stock_code} 不存在")

    target = trade_date or await latest_minute_day(session, stock_code)
    if target is None:
        return {
            "code": stock_code,
            "name": stock.stock_name or stock_code,
            "trade_date": date.today(),
            "prev_close": 0.0,
            "points": [],
        }

    bars = await fetch_minute_bars(session, stock_code, target)
    prev_close = await prev_minute_close(session, stock_code, target)
    if prev_close is None:
        daily = await fetch_daily_bars(session, stock_code, end_date=target, limit=2)
        earlier = [bar for bar in daily if bar.trade_date < target and bar.close]
        prev_close = _to_float(earlier[0].close) if earlier else None
    if prev_close is None:
        prev_close = _to_float(bars[0].close) if bars and bars[0].close else 0.0

    points = [
        {
            "time": bar.trade_time.astimezone(_CN_TZ).strftime("%H:%M"),
            "price": _to_float(bar.close) or 0.0,
            "volume": _to_int(bar.volume) or 0,
            "amount": _to_float(bar.amount) or 0.0,
        }
        for bar in bars
    ]
    return {
        "code": stock_code,
        "name": stock.stock_name or stock_code,
        "trade_date": target,
        "prev_close": prev_close,
        "points": points,
    }
