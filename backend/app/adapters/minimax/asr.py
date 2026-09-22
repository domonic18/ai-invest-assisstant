"""MiniMax speech_to_text 共享核心：kb 分片转写与社媒单音频/样例测试共用。

职责止于传输：URL 归一（``normalize_asr_base``）+ Bearer + multipart 上传 +
429/5xx 退避重试（backoff 可配置，空元组即不重试）。base_resp 业务错误的
识别提供 :func:`parse_business_error`，错误消息策略（归因码/降级文案）由
调用方按各自契约决定；响应形态解析（verbose_json 句级时间码 / 纯 text）
同样归调用方。
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.utils.api_base import normalize_asr_base

logger = structlog.get_logger(__name__)

#: 渠道偶发 5xx/429（观测与 200+空返回同为抖动形态），退避重试
_RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


class MiniMaxAsrHttpError(Exception):
    """HTTP 层失败（状态码非 2xx 或网络/解析错误）。"""


@dataclass(slots=True)
class SpeechToTextRequest:
    """一次转写调用的全部参数。"""

    base_url: str
    api_key: str
    model: str
    filename: str
    audio: bytes
    content_type: str
    response_format: str
    timeout_seconds: float
    retry_backoff_seconds: tuple[float, ...] = ()
    extra_data: dict[str, str] = field(default_factory=dict)


def parse_business_error(payload: dict[str, Any]) -> tuple[int, str] | None:
    """识别业务错误形态（HTTP 200 + base_resp.status_code != 0）。

    Returns:
        (status_code, status_msg)；无业务错误返回 None。
    """
    base_resp = payload.get("base_resp")
    if isinstance(base_resp, dict) and base_resp.get("status_code"):
        status_msg = base_resp.get("status_msg") or "未知错误"
        return int(base_resp["status_code"]), status_msg
    return None


async def speech_to_text(request: SpeechToTextRequest) -> dict[str, Any]:
    """发起转写请求；可重试状态码按 backoff 退避，最终失败抛 MiniMaxAsrHttpError。"""
    url = f"{normalize_asr_base(request.base_url)}/v1/speech_to_text"
    data = {
        "model": request.model,
        "response_format": request.response_format,
        **request.extra_data,
    }
    for attempt in range(len(request.retry_backoff_seconds) + 1):
        if attempt:
            await asyncio.sleep(request.retry_backoff_seconds[attempt - 1])
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {request.api_key}"},
                    data=data,
                    files={
                        "file": (request.filename, request.audio, request.content_type)
                    },
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
                return payload
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if (
                status not in _RETRYABLE_HTTP_STATUSES
                or attempt >= len(request.retry_backoff_seconds)
            ):
                raise MiniMaxAsrHttpError(f"asr_http_{status}") from exc
            logger.warning("minimax_asr_http_retry", status=status, attempt=attempt + 1)
        except Exception as exc:  # noqa: BLE001
            raise MiniMaxAsrHttpError(f"asr_request_failed: {exc}") from exc
    raise MiniMaxAsrHttpError("asr_http_retry_exhausted")  # pragma: no cover — 逻辑不可达
