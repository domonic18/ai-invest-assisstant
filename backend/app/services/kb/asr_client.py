"""asr-1.0 分片客户端：multipart 上传 wav、verbose_json 句级时间码解析。

HTTP 往返与 429/5xx 重试经 :mod:`app.adapters.minimax.asr` 共享核心；本模块
保留知识库长音频分片语义：句级时间码容忍解析、业务错误抛
:class:`AsrChannelError`（message 直接作为 process_error 归因，不静默重试
烧钱）。
"""

from dataclasses import dataclass
from typing import Any

import structlog

from app.adapters.minimax import asr as minimax_asr
from app.adapters.minimax.asr import MiniMaxAsrHttpError
from app.models.social import AsrChannelConfig
from app.services.kb.transcribe_pipeline import Sentence

logger = structlog.get_logger(__name__)

#: 分片 ≤480s，转写耗时上限留一倍余量
_ASR_CHUNK_TIMEOUT_SECONDS = 600.0
#: 渠道偶发 5xx/429（观测与 200+空返回同为抖动形态），退避重试
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


async def transcribe_chunk(
    config: AsrChannelConfig, api_key: str, wav: bytes, *, filename: str
) -> ChunkTranscript:
    """转写单个 wav 分片；渠道/业务错误抛 AsrChannelError。"""
    try:
        payload = await minimax_asr.speech_to_text(
            minimax_asr.SpeechToTextRequest(
                base_url=config.base_url or "",
                api_key=api_key,
                model=config.model,
                filename=filename,
                audio=wav,
                content_type="audio/wav",
                response_format="verbose_json",
                timeout_seconds=_ASR_CHUNK_TIMEOUT_SECONDS,
                retry_backoff_seconds=_HTTP_RETRY_BACKOFF_SECONDS,
                extra_data={"timestamp_level": "sentence"},
            )
        )
    except MiniMaxAsrHttpError as exc:
        raise AsrChannelError(str(exc)) from exc

    business = minimax_asr.parse_business_error(payload)
    if business is not None:
        raise AsrChannelError(f"asr_business_{business[0]}: {business[1]}")

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
