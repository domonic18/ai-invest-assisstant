"""模拟盘柜台报文的标量值转换（类型宽松的原始值 → Python 强类型）。

柜台（Go sidecar）报文类型宽松：float32 尾噪（6.46999979019165）、epoch
秒/毫秒混用、字段缺失或多候选键并存。本模块只做值级收敛，不接触 ORM 与
HTTP；行级组装见 ``paper_trade_mappers``。
"""

import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.core.clock import CN_TZ

# 回报幂等键：暂定柜台 ex_exec_id，缺失时回退 cl_ord_id+时间组合（实抓字段为准后可回填）
EXEC_ID_KEYS = ("ex_exec_id", "exec_id")

BARE_CODE_RE = re.compile(r"\d{6}")

# 柜台（Go sidecar）float32 数值带尾噪声（6.46999979019165），wire 前统一 quantize
_Q_EXP_2 = Decimal("0.01")
_Q_EXP_4 = Decimal("0.0001")


def unwrap_rows(raw: Any) -> list[dict[str, Any]]:
    """柜台列表端点解包后可能为 {}（空结果），统一收敛为 list[dict]。"""
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def bare_stock_code(symbol: str) -> str:
    """掘金代码 SHSE.600000 → 6 位代码。"""
    return symbol.split(".", 1)[1] if "." in symbol else symbol


def parse_counter_datetime(value: Any) -> datetime | None:
    """柜台时间字段容错解析：epoch 秒/毫秒或 ISO 字符串 → aware UTC。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:  # 毫秒时间戳
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def counter_cn_trade_date(counter_dt: datetime | None, fallback: date) -> date:
    """业务日 = 柜台时间的 CN 日历日；时间缺失回退同步目标日。"""
    return counter_dt.astimezone(CN_TZ).date() if counter_dt else fallback


def to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def to_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_present(data: dict[str, Any], *keys: str) -> Any:
    """持仓字段多候选键提取（柜台真实字段名待首次成交实抓后收敛）。"""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def quantize_2dp(value: Decimal | None) -> Decimal | None:
    """金额 quantize 到分（四舍五入）。"""
    return None if value is None else value.quantize(_Q_EXP_2, rounding=ROUND_HALF_UP)


def quantize_4dp(value: Decimal | None) -> Decimal | None:
    """价格 quantize 到 0.0001（四舍五入）。"""
    return None if value is None else value.quantize(_Q_EXP_4, rounding=ROUND_HALF_UP)
