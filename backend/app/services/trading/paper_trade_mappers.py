"""模拟盘柜台报文 → 本地行 / wire 行的组装（converter 之上的行级纯转换）。

``normalize_*`` 产出 upsert 用 dict 行；``*_wire_row`` 产出 API wire 行
（camelCase 由 schema 层出，此处 snake 键构造）。只做纯转换，不做 IO。
"""

from datetime import date
from decimal import Decimal
from typing import Any

import structlog

from app.services.trading.paper_trade_converters import (
    EXEC_ID_KEYS,
    bare_stock_code,
    counter_cn_trade_date,
    first_present,
    parse_counter_datetime,
    quantize_2dp,
    quantize_4dp,
    to_decimal,
    to_int,
    unwrap_rows,
)

logger = structlog.get_logger(__name__)


def normalize_order_rows(
    raw: Any,
    fallback_date: date,
    *,
    account_id: int,
    order_source: str,
) -> list[dict[str, Any]]:
    """柜台委托对象 → paper_trade_order 行（缺 cl_ord_id 的行跳过并告警）。"""
    rows: list[dict[str, Any]] = []
    for item in unwrap_rows(raw):
        cl_ord_id = str(item.get("cl_ord_id") or "").strip()
        if not cl_ord_id:
            logger.warning("paper_trade_order_missing_cl_ord_id", raw=item)
            continue
        symbol = str(item.get("symbol") or "")
        created = parse_counter_datetime(item.get("created_at"))
        rows.append(
            {
                "paper_trade_account_id": account_id,
                "order_source": order_source,
                "cl_ord_id": cl_ord_id,
                "trade_date": counter_cn_trade_date(
                    created or parse_counter_datetime(item.get("updated_at")),
                    fallback_date,
                ),
                "symbol": symbol,
                "stock_code": bare_stock_code(symbol),
                "side": to_int(item.get("side")) or 0,
                "order_type": to_int(item.get("order_type")) or 0,
                "position_effect": to_int(item.get("position_effect")) or 1,
                "price": to_decimal(item.get("price")) or Decimal("0"),
                "volume": to_int(item.get("volume")) or 0,
                "status": to_int(item.get("status")) or 0,
                "ord_rej_reason": to_int(item.get("ord_rej_reason")),
                "ord_rej_reason_detail": item.get("ord_rej_reason_detail"),
                "counter_created_at": created,
                "counter_updated_at": parse_counter_datetime(item.get("updated_at")),
                "raw": item,
            }
        )
    return rows


def normalize_execution_rows(
    raw: Any,
    fallback_date: date,
    *,
    account_id: int,
) -> list[dict[str, Any]]:
    """柜台回报对象 → paper_trade_execution 行（幂等键缺失时回退组合键）。"""
    rows: list[dict[str, Any]] = []
    for item in unwrap_rows(raw):
        exec_id = next(
            (str(item[key]).strip() for key in EXEC_ID_KEYS if item.get(key)), ""
        )
        cl_ord_id = str(item.get("cl_ord_id") or "").strip()
        created = parse_counter_datetime(item.get("created_at"))
        if not exec_id:
            if not (cl_ord_id and created):
                logger.warning("paper_trade_execution_missing_exec_id", raw=item)
                continue
            exec_id = f"{cl_ord_id}:{created.isoformat()}"
        symbol = str(item.get("symbol") or "")
        price = to_decimal(item.get("price"))
        volume = to_int(item.get("volume"))
        turnover = to_decimal(item.get("turnover"))
        if turnover is None and price is not None and volume:
            # 掘金回报不带成交额：按 价×量 本地补算（与股票软件口径一致）
            turnover = quantize_2dp(price * volume)
        rows.append(
            {
                "paper_trade_account_id": account_id,
                "exec_id": exec_id,
                "cl_ord_id": cl_ord_id,
                "trade_date": counter_cn_trade_date(created, fallback_date),
                "symbol": symbol,
                "side": to_int(item.get("side")),
                "exec_type": to_int(item.get("exec_type")),
                "price": price,
                "volume": volume,
                "turnover": turnover,
                "commission": to_decimal(item.get("commission")),
                "counter_created_at": created,
                "raw": item,
            }
        )
    return rows


def normalize_cash_row(raw: Any, trade_date: date) -> dict[str, Any]:
    """柜台资金概况 → paper_trade_cash_snapshot 行（一日一行，账户维度由调用方补齐）。

    柜台对单对象也包数组返回（实测 ``[ {...} ]``），取首个 dict。
    """
    if isinstance(raw, list):
        data = next((row for row in raw if isinstance(row, dict)), {})
    elif isinstance(raw, dict):
        data = raw
    else:
        data = {}
    return {
        "trade_date": trade_date,
        "nav": to_decimal(data.get("nav")),
        "available": to_decimal(data.get("available")),
        "balance": to_decimal(data.get("balance")),
        "cum_inout": to_decimal(data.get("cum_inout")),
        "last_inout": to_decimal(data.get("last_inout")),
    }


def order_wire_row(item: dict[str, Any], fallback_date: date) -> dict[str, Any]:
    """柜台委托对象 → wire 行（camelCase 由 schema 层出，此处 snake 键构造）。"""
    symbol = str(item.get("symbol") or "")
    created = parse_counter_datetime(item.get("created_at"))
    return {
        "cl_ord_id": str(item.get("cl_ord_id") or ""),
        "trade_date": counter_cn_trade_date(created, fallback_date),
        "symbol": symbol,
        "stock_code": bare_stock_code(symbol),
        "side": to_int(item.get("side")) or 0,
        "order_type": to_int(item.get("order_type")) or 0,
        "position_effect": to_int(item.get("position_effect")) or 1,
        "price": to_decimal(item.get("price")) or Decimal("0"),
        "volume": to_int(item.get("volume")) or 0,
        "status": to_int(item.get("status")) or 0,
        "ord_rej_reason": to_int(item.get("ord_rej_reason")),
        "ord_rej_reason_detail": item.get("ord_rej_reason_detail"),
        "counter_created_at": created,
        "counter_updated_at": parse_counter_datetime(item.get("updated_at")),
    }


def position_wire_row(item: dict[str, Any]) -> dict[str, Any]:
    """柜台持仓对象 → wire 行（字段名多候选容错，缺失项为 None）。

    柜台 float32 噪声与浮盈缺失在此收敛：价格/金额 quantize；
    profit/profit_rate 柜台未给时按 (现价-成本)×数量 本地补算（同 A 股软件口径）。
    """
    symbol = str(item.get("symbol") or "")
    volume = to_int(first_present(item, "volume", "total_volume"))
    avg_price = quantize_4dp(
        to_decimal(first_present(item, "price", "vwap", "avg_price", "open_price"))
    )
    last_price = quantize_4dp(
        to_decimal(first_present(item, "last_price", "current_price", "close"))
    )
    profit = quantize_2dp(
        to_decimal(first_present(item, "profit", "float_profit", "position_profit"))
    )
    profit_rate = quantize_4dp(to_decimal(first_present(item, "profit_rate", "profit_ratio")))
    if profit is None and volume and avg_price is not None and last_price is not None:
        profit = quantize_2dp((last_price - avg_price) * volume)
    if profit_rate is None and profit is not None and volume and avg_price:
        profit_rate = quantize_4dp(profit / (avg_price * volume) * 100)
    return {
        "symbol": symbol,
        "stock_code": bare_stock_code(symbol),
        "side": to_int(item.get("side")),
        "volume": volume,
        "available_volume": to_int(
            first_present(item, "available_volume", "avail_volume", "available")
        ),
        "avg_price": avg_price,
        "last_price": last_price,
        "market_value": quantize_2dp(
            to_decimal(first_present(item, "market_value", "position_value"))
        ),
        "profit": profit,
        "profit_rate": profit_rate,
    }
