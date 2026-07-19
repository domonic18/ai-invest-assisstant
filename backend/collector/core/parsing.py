"""Spider 共享解析工具 — 各采集器私有 _str/_to_float/_clean_code 的唯一实现。"""

import re
from datetime import date, datetime, time
from typing import Any

_AMOUNT_UNITS = {
    "万": 10_000,
    "亿": 100_000_000,
    "万亿": 1_000_000_000_000,
}

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d")
_TIME_FORMATS = ("%H:%M:%S", "%H:%M")

_MARKET_PREFIXES = ("sh", "sz", "bj")


def is_nan(value: Any) -> bool:
    """判断 float NaN（pandas 缺失值）。"""
    return isinstance(value, float) and value != value  # noqa: PLR0124


def to_optional_str(value: Any) -> str | None:
    """转为去空白字符串，空值/空串/NaN 返回 None。"""
    if value is None or is_nan(value):
        return None
    text = str(value).strip()
    return text if text else None


def to_float(value: Any) -> float | None:
    """容错转 float，无法解析或 NaN 返回 None。"""
    if value is None or is_nan(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if result != result else result  # noqa: PLR0124


def to_int(value: Any) -> int | None:
    """容错转 int，无法解析返回 None。"""
    if value is None or is_nan(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_cn_amount(value: Any) -> float | None:
    """解析带中文单位（万/亿/万亿）的金额（可带"元"后缀），无法解析返回 None。"""
    if value is None or is_nan(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*([万亿万])?元?$", text)
    if not match:
        try:
            return float(text)
        except (TypeError, ValueError):
            return None
    number = float(match.group(1))
    unit = match.group(2)
    return number * _AMOUNT_UNITS.get(unit, 1)


def clean_stock_code(symbol: Any) -> str:
    """去除股票代码的 sh/sz/bj 市场前缀并去空白。"""
    code = str(symbol).strip().lower()
    for prefix in _MARKET_PREFIXES:
        if code.startswith(prefix):
            return code[len(prefix):]
    return code


def parse_date(value: Any) -> date | None:
    """容错解析日期（支持 date/datetime/常见字符串格式），失败返回 None。"""
    if value is None or is_nan(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(value: Any) -> time | None:
    """容错解析时间（支持 time/datetime/常见字符串格式），失败返回 None。"""
    if value is None or is_nan(value):
        return None
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None
