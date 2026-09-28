"""ASR 分片客户端单测：协议端点分派、429/5xx 退避重试、业务错误与空结果归因（HTTP 全 fake）。"""

from typing import Any

import httpx
import pytest

from app.adapters import asr as asr_adapter
from app.adapters.asr import asr_endpoint
from app.adapters.asr.core import httpx as asr_httpx
from app.models.social import AsrChannelConfig
from app.services.kb import asr_client
from app.services.kb.asr_client import (
    AsrChannelError,
    AsrEmptyResultError,
    AsrRateLimitedError,
)

pytestmark = pytest.mark.unit


def _config(protocol: str = "minimax") -> AsrChannelConfig:
    return AsrChannelConfig(
        id=1,
        provider="minimax" if protocol == "minimax" else "custom",
        protocol=protocol,
        base_url="https://api.minimaxi.com" if protocol == "minimax" else "http://localhost:8080",
        model="asr-1.0" if protocol == "minimax" else "whisper-large-v3",
        api_key_encrypted="enc",
        enabled=True,
    )


_MINIMAX_URL = "https://api.minimaxi.com/v1/speech_to_text"


@pytest.mark.parametrize(
    ("base_url", "protocol", "expected"),
    [
        # minimax：剥 /v1 后自拼专有路径
        ("https://api.minimaxi.com", "minimax", "https://api.minimaxi.com/v1/speech_to_text"),
        (
            "https://api.minimaxi.com/v1/speech_to_text",
            "minimax",
            "https://api.minimaxi.com/v1/speech_to_text",
        ),
        # openai 兼容：裸主机补 /v1，带路径原样保留
        ("http://localhost:8080", "openai", "http://localhost:8080/v1/audio/transcriptions"),
        (
            "https://api.groq.com/openai/v1",
            "openai",
            "https://api.groq.com/openai/v1/audio/transcriptions",
        ),
        (
            "https://api.siliconflow.cn/v1/audio/transcriptions",
            "openai",
            "https://api.siliconflow.cn/v1/audio/transcriptions",
        ),
    ],
)
def test_asr_endpoint_dispatch(base_url: str, protocol: str, expected: str) -> None:
    assert asr_endpoint(base_url, protocol) == expected


def test_asr_endpoint_unknown_protocol_raises() -> None:
    with pytest.raises(ValueError, match="未知 ASR 协议"):
        asr_endpoint("https://example.com", "weird")


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", _MINIMAX_URL)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"{status}", request=request, response=response)


def _ok(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, request=httpx.Request("POST", _MINIMAX_URL), json=payload)


class _FakeClient:
    """按 effects 序列回放：异常直接抛，httpx.Response 原样返回；记录请求供断言。"""

    def __init__(self, effects: list[Any]) -> None:
        self.effects = list(effects)
        self.calls = 0
        self.seen: list[dict[str, Any]] = []

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> Any:
        self.calls += 1
        self.seen.append({"url": url, "data": kwargs.get("data")})
        effect = self.effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


def _patch_client(monkeypatch: pytest.MonkeyPatch, effects: list[Any]) -> _FakeClient:
    fake = _FakeClient(effects)
    monkeypatch.setattr(asr_httpx, "AsyncClient", lambda **kwargs: fake)
    monkeypatch.setattr(asr_client, "_HTTP_RETRY_BACKOFF_SECONDS", (0.0, 0.0))
    return fake


async def test_minimax_protocol_sends_vendor_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _patch_client(monkeypatch, [_ok({"text": "你好世界"})])
    result = await asr_client.transcribe_chunk(
        _config(), "key", b"wav", filename="chunk.wav"
    )
    assert [s.text for s in result.sentences] == ["你好世界"]
    assert fake.seen[0]["url"] == _MINIMAX_URL
    assert fake.seen[0]["data"] == {
        "model": "asr-1.0",
        "response_format": "verbose_json",
        "timestamp_level": "sentence",  # MiniMax 专有参数
    }


async def test_openai_protocol_no_vendor_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """openai 兼容协议：裸主机补 /v1 的端点 + 不发 MiniMax 专有参数。"""
    fake = _patch_client(monkeypatch, [_ok({"text": "hello"})])
    result = await asr_client.transcribe_chunk(
        _config("openai"), "key", b"wav", filename="chunk.wav"
    )
    assert [s.text for s in result.sentences] == ["hello"]
    assert fake.seen[0]["url"] == "http://localhost:8080/v1/audio/transcriptions"
    assert fake.seen[0]["data"] == {"model": "whisper-large-v3", "response_format": "verbose_json"}


async def test_unknown_protocol_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """脏协议数据显式报错而非静默走错端点（HTTP 调用不发生）。"""
    fake = _patch_client(monkeypatch, [_ok({"text": "x"})])
    with pytest.raises(ValueError, match="未知 ASR 协议"):
        await asr_client.transcribe_chunk(
            _config("weird"), "key", b"wav", filename="c.wav"
        )
    assert fake.calls == 0


async def test_retryable_500_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_client(monkeypatch, [_status_error(500), _ok({"text": "你好世界"})])
    result = await asr_client.transcribe_chunk(
        _config(), "key", b"wav", filename="chunk.wav"
    )
    assert [s.text for s in result.sentences] == ["你好世界"]
    assert fake.calls == 2


async def test_retryable_500_exhausts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_client(
        monkeypatch, [_status_error(500), _status_error(502), _status_error(503)]
    )
    with pytest.raises(AsrChannelError, match="asr_http_503"):
        await asr_client.transcribe_chunk(_config(), "key", b"wav", filename="c.wav")
    assert fake.calls == 3  # 首次 + 两次重试


async def test_429_exhausts_raises_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 退避耗尽抛 AsrRateLimitedError（调用方据此暂缓而非终态失败）。"""
    fake = _patch_client(
        monkeypatch, [_status_error(429), _status_error(429), _status_error(429)]
    )
    with pytest.raises(AsrRateLimitedError, match="asr_http_429"):
        await asr_client.transcribe_chunk(_config(), "key", b"wav", filename="c.wav")
    assert fake.calls == 3


async def test_non_retryable_400_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_client(monkeypatch, [_status_error(400), _status_error(400)])
    with pytest.raises(AsrChannelError, match="asr_http_400"):
        await asr_client.transcribe_chunk(_config(), "key", b"wav", filename="c.wav")
    assert fake.calls == 1


async def test_business_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        [_ok({"base_resp": {"status_code": 1004, "status_msg": "配额不足"}})],
    )
    with pytest.raises(AsrChannelError, match="asr_business_1004"):
        await asr_client.transcribe_chunk(_config(), "key", b"wav", filename="c.wav")


async def test_empty_payload_raises_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, [_ok({"text": ""})])
    with pytest.raises(AsrEmptyResultError):
        await asr_client.transcribe_chunk(_config(), "key", b"wav", filename="c.wav")
