"""base_url 归一化契约：容忍用户粘贴完整端点。"""

import pytest

from app.utils.api_base import normalize_api_base, normalize_asr_base

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 规范根地址原样保留（含尾斜杠容忍）
        ("https://api.deepseek.com", "https://api.deepseek.com"),
        ("https://open.bigmodel.cn/api/paas/v4", "https://open.bigmodel.cn/api/paas/v4"),
        ("https://api.openai.com/v1/", "https://api.openai.com/v1"),
        ("  https://host/v1  ", "https://host/v1"),
        # 粘贴完整端点 → 剥端点后缀，保留版本段
        ("https://open.bigmodel.cn/api/paas/v4/embeddings", "https://open.bigmodel.cn/api/paas/v4"),
        ("https://api.openai.com/v1/chat/completions", "https://api.openai.com/v1"),
        ("https://api.kimi.com/coding/v1/messages", "https://api.kimi.com/coding"),
        ("https://asr.host/v1/speech_to_text", "https://asr.host/v1"),
        # 空值防御
        ("", ""),
    ],
)
def test_normalize_api_base(raw: str, expected: str) -> None:
    assert normalize_api_base(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # ASR 客户端自拼 /v1/speech_to_text，根地址不含版本段
        ("https://asr.host", "https://asr.host"),
        ("https://asr.host/v1/speech_to_text", "https://asr.host"),
        ("https://asr.host/v1/", "https://asr.host"),
    ],
)
def test_normalize_asr_base(raw: str, expected: str) -> None:
    assert normalize_asr_base(raw) == expected
