"""token 估算兜底（无协议 usage 时的启发式）。

不引入 tokenizer 库（模型方言不一、依赖重）：CJK 字符记 1 token、
其他字符记 0.25 token，向上取整。仅用于预扣与 estimated 口径，
真实 usage 可得时不用本函数。
"""

import math


def estimate_text_tokens(text: str | None) -> int:
    """按 CJK/非 CJK 字符启发式估算 token 数。"""
    if not text:
        return 0
    cjk = 0
    for ch in text:
        code = ord(ch)
        # CJK 统一表意、扩展A、兼容表意、假名、注音、全角符号区块
        if 0x2E80 <= code <= 0x9FFF or 0x3040 <= code <= 0x30FF or 0xF900 <= code <= 0xFAFF or 0xFF00 <= code <= 0xFF60:
            cjk += 1
    other = len(text) - cjk
    return math.ceil(cjk + other * 0.25)
