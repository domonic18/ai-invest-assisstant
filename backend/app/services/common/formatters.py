"""金额展示格式化（纯函数，无 IO）。

同族两个格式化器是**有意的口径差异**，按展示场景选用，不要合并成参数化函数：
- ``format_amount``：智能档位，适配大盘成交额等万亿/亿跨量级场景；
- ``format_amount_yi``：固定亿元一位小数，适配板块主力净流入等亿量级
  紧凑上下文（万亿档位反而损失可读性）。
"""


def format_amount(amount: float | None) -> str:
    """智能档位：≥1 万亿显示"X.XX 万亿元"（两位小数），否则"X 亿元"（整数）。"""
    if amount is None:
        return "未知"
    if amount >= 1e12:
        return f"{amount / 1e12:.2f} 万亿元"
    return f"{amount / 1e8:.0f} 亿元"


def format_amount_yi(amount: float | None) -> str:
    """固定亿元一位小数，不做档位切换。"""
    if amount is None:
        return "未知"
    return f"{amount / 1e8:.1f} 亿元"
