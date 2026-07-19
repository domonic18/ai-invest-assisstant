"""Shared parsing helpers for collector spiders."""

import re
from typing import Any

_AMOUNT_UNITS = {
    "万": 10_000,
    "亿": 100_000_000,
    "万亿": 1_000_000_000_000,
}


def to_optional_str(value: Any) -> str | None:
    """转为去空白字符串，空值/空串返回 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def parse_cn_amount(value: Any) -> float | None:
    """解析带中文单位（万/亿/万亿）的金额，无法解析返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*([万亿万])?$", text)
    if not match:
        try:
            return float(text)
        except (TypeError, ValueError):
            return None
    number = float(match.group(1))
    unit = match.group(2)
    return number * _AMOUNT_UNITS.get(unit, 1)
