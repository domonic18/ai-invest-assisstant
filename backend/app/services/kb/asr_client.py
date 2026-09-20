"""asr-1.0 分片客户端：multipart 上传 wav、verbose_json 句级时间码解析。

与 social/asr_service（电报单音频、纯文本）不同：本模块面向知识库长音频
分片，要求句级时间戳；业务错误（HTTP 200 + base_resp.status_code != 0）
抛 :class:`AsrChannelError`，由调用方显式 FAILED 归因，不静默重试烧钱。
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.models.social import AsrChannelConfig
from app.services.kb.transcribe_pipeline import Sentence
from app.utils.api_base import normalize_asr_base

logger = structlog.get_logger(__name__)

#: 分片 ≤480s，转写耗时上限留一倍余量
_ASR_CHUNK_TIMEOUT_SECONDS = 600.0
#: 渠道偶发 5xx/429（观测与 200+空返回同为抖动形态），退避重试
_RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
_HTTP_RETRY_BACKOFF_SECONDS = (3.0, 6.0)

_TIME_KEYS = ("start_time", "start", "begin", "from")
_END_KEYS = ("end_time", "end", "to")
_LIST_KEYS = ("sentences", "segments", "utterances")


class AsrChannelError(Exception):
    """ASR 渠道不可用/业务错误（message 直接作为 process_error 归因）。"""


class AsrEmptyResultError(AsrChannelError):
    """渠道 200 但无任何转写内容（观测为偶发，重试后通常恢复）。"""


@dataclass(slots=True)
class ChunkTranscript:
    """单分片转写产物。"""

    sentences: list[Sentence]
    audio_seconds: float | None = None


def normalize_ms(value: float) -> int:
    """时间码归一为毫秒：分片 ≤480s，故 ≤480 视为秒、更大值视为毫秒。"""
    return int(round(value * 1000)) if value <= 480 else int(round(value))


def parse_verbose_json(payload: dict[str, Any]) -> list[Sentence]:
    """容忍解析 verbose_json：sentences/segments/utterances 任一数组。"""
    raw_items: list[dict[str, Any]] = []
    for key in _LIST_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            raw_items = [item for item in value if isinstance(item, dict)]
            break
    sentences: list[Sentence] = []
    for item in raw_items:
        text = item.get("text")
        start = next((item[k] for k in _TIME_KEYS if isinstance(item.get(k), (int, float))), None)
        end = next((item[k] for k in _END_KEYS if isinstance(item.get(k), (int, float))), None)
        if not isinstance(text, str) or start is None or end is None:
            continue
        sentences.append(
            Sentence(start_ms=normalize_ms(start), end_ms=normalize_ms(end), text=text)
        )
    return sentences


async def _post_chunk(
    base_url: str, config: AsrChannelConfig, api_key: str, wav: bytes, *, filename: str
) -> dict[str, Any]:
    """发起转写请求，429/5xx 指数退避重试两次，其余错误立即归因。"""
    for attempt in range(len(_HTTP_RETRY_BACKOFF_SECONDS) + 1):
        if attempt:
            await asyncio.sleep(_HTTP_RETRY_BACKOFF_SECONDS[attempt - 1])
        try:
            async with httpx.AsyncClient(timeout=_ASR_CHUNK_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{base_url}/v1/speech_to_text",
                    headers={"Authorization": f"Bearer {api_key}"},
                    data={
                        "model": config.model,
                        "response_format": "verbose_json",
                        "timestamp_level": "sentence",
                    },
                    files={"file": (filename, wav, "audio/wav")},
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
                return payload
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if (
                status not in _RETRYABLE_HTTP_STATUSES
                or attempt >= len(_HTTP_RETRY_BACKOFF_SECONDS)
            ):
                raise AsrChannelError(f"asr_http_{status}") from exc
            logger.warning("kb_asr_http_retry", status=status, attempt=attempt + 1)
        except Exception as exc:  # noqa: BLE001
            raise AsrChannelError(f"asr_request_failed: {exc}") from exc
    raise AsrChannelError("asr_http_retry_exhausted")  # pragma: no cover — 逻辑不可达


async def transcribe_chunk(
    config: AsrChannelConfig, api_key: str, wav: bytes, *, filename: str
) -> ChunkTranscript:
    """转写单个 wav 分片；渠道/业务错误抛 AsrChannelError。"""
    base_url = normalize_asr_base(config.base_url or "")
    payload = await _post_chunk(base_url, config, api_key, wav, filename=filename)

    base_resp = payload.get("base_resp")
    if isinstance(base_resp, dict) and base_resp.get("status_code"):
        raise AsrChannelError(
            f"asr_business_{base_resp['status_code']}: "
            f"{base_resp.get('status_msg') or '未知错误'}"
        )

    sentences = parse_verbose_json(payload)
    if not sentences:
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            # 渠道未回时间戳时退化为整片一句（起点 0，终点按片长）
            return ChunkTranscript(
                [Sentence(0, int((payload.get("duration") or 0) * 1000) or 0, text.strip())]
            )
        raise AsrEmptyResultError("asr_empty_result")
    duration = payload.get("duration")
    audio_seconds = float(duration) if isinstance(duration, (int, float)) else None
    logger.debug(
        "kb_asr_chunk_ok", filename=filename, sentences=len(sentences)
    )
    return ChunkTranscript(sentences, audio_seconds)
