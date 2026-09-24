"""token 估算兜底（CJK/非 CJK 启发式）单测。"""

import pytest

from app.agent.runtime.token_estimator import estimate_text_tokens

pytestmark = pytest.mark.unit


def test_empty_and_none() -> None:
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens(None) == 0


def test_pure_cjk() -> None:
    # CJK 每字 1 token
    assert estimate_text_tokens("复盘") == 2
    assert estimate_text_tokens("涨停板分析") == 5


def test_pure_ascii() -> None:
    # 非 CJK 每字符 0.25，向上取整
    assert estimate_text_tokens("abcd") == 1
    assert estimate_text_tokens("abc") == 1  # 0.75 → ceil 1
    assert estimate_text_tokens("abcdefgh") == 2


def test_mixed() -> None:
    # 3 CJK + 8 ascii = 3 + 2
    assert estimate_text_tokens("复盘abcd efgh") == 5


def test_full_width_and_kana_count_as_cjk() -> None:
    # 全角标点与假名按 CJK 计
    assert estimate_text_tokens("，。") == 2
    assert estimate_text_tokens("あいう") == 3
