"""asr-1.0 分片客户端单测：429/5xx 退避重试、业务错误与空结果归因（HTTP 全 fake）。"""

from typing import Any

import httpx
import pytest

from app.adapters.minimax import asr as minimax_asr
from app.models.social import AsrChannelConfig
from app.services.kb import asr_client
from app.services.kb.asr_client import AsrChannelError, AsrEmptyResultError

pytestmark = pytest.mark.unit


def _config() -> AsrChannelConfig:
    return AsrChannelConfig(
        id=1,
        provider="minimax",
        base_url="https://api.minimaxi.com",
        model="asr-1.0",
        api_key_encrypted="enc",
        enabled=True,
    )


_URL = "https://api.minimaxi.com/v1/speech_to_text"


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", _URL)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"{status}", request=request, response=response)


def _ok(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, request=httpx.Request("POST", _URL), json=payload)


class _FakeClient:
    """按 effects 序列回放：异常直接抛，httpx.Response 原样返回。"""

    def __init__(self, effects: list[Any]) -> None:
        self.effects = list(effects)
        self.calls = 0

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        effect = self.effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


def _patch_client(monkeypatch: pytest.MonkeyPatch, effects: list[Any]) -> _FakeClient:
    fake = _FakeClient(effects)
    monkeypatch.setattr(minimax_asr.httpx, "AsyncClient", lambda **kwargs: fake)
    monkeypatch.setattr(asr_client, "_HTTP_RETRY_BACKOFF_SECONDS", (0.0, 0.0))
    return fake


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
