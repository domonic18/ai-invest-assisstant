"""龙虎榜助手工具（异动归因证据查询）。"""

from datetime import date, timedelta
from typing import Any

from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal
from app.repositories.market import dragon_tiger_repository

STOCK_WINDOW_DAYS = 90
BOARD_ROW_CAP = 50
STOCK_ROW_CAP = 20


def _parse_date(value: str | None) -> tuple[date | None, str | None]:
    """解析可选 ISO 日期参数；返回 (日期, None) 或 (None, 错误提示)。"""
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "trade_date 须为 YYYY-MM-DD 格式"


def _row(row: Any) -> dict[str, Any]:
    return {
        "trade_date": row.trade_date.isoformat(),
        "stock_code": row.stock_code,
        "stock_name": row.stock_name,
        "rank_reason": row.rank_reason,
        "close_price": float(row.close_price) if row.close_price is not None else None,
        "change_pct": float(row.change_pct) if row.change_pct is not None else None,
        "net_buy_amount_yi": (
            round(float(row.net_buy_amount) / 1e8, 2)
            if row.net_buy_amount is not None
            else None
        ),
    }


@tool
async def get_dragon_tiger(
    stock_code: str | None = None, trade_date: str | None = None
) -> dict[str, Any]:
    """查询龙虎榜上榜记录：某股近期上榜明细，或指定交易日的上榜全表。净买额单位亿元。

    Args:
        stock_code: 6 位股票代码（如 "000001"）时返回该股近 90 个自然日上榜记录；
            缺省时按 trade_date 查询当日榜单。
        trade_date: 交易日（YYYY-MM-DD），stock_code 缺省时生效；缺省为最近交易日。
    """
    from app.services.market import trade_calendar_service

    resolved, error = _parse_date(trade_date)
    if error:
        return {"error": error}

    async with AsyncSessionLocal() as session:
        if stock_code:
            end = resolved or await trade_calendar_service.resolve_latest_trade_date(
                session
            )
            if end is None:
                return {"error": "交易日历为空，无法确定查询窗口"}
            rows = await dragon_tiger_repository.list_by_stock(
                session,
                stock_code,
                start_date=end - timedelta(days=STOCK_WINDOW_DAYS),
                end_date=end,
            )
            return {
                "stock_code": stock_code,
                "window_end": end.isoformat(),
                "items": [_row(row) for row in rows[:STOCK_ROW_CAP]],
            }

        target = resolved or await trade_calendar_service.resolve_latest_trade_date(
            session
        )
        if target is None:
            return {"error": "交易日历为空，无法确定查询日期"}
        rows = await dragon_tiger_repository.list_by_date(session, target)
        return {
            "trade_date": target.isoformat(),
            "unit": "net_buy_amount_yi 单位为亿元",
            "total": len(rows),
            "items": [_row(row) for row in rows[:BOARD_ROW_CAP]],
        }
