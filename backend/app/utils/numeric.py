"""数值计算工具：跨 service / agent 共享。"""

from decimal import Decimal


def safe_divide(
    numerator: Decimal | float | None, denominator: Decimal | float | None
) -> float | None:
    """安全除法，分母为空或为零时返回 None。"""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)
