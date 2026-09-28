"""转写（ASR）适配层：多厂商 speech-to-text 共享 HTTP 核心（协议分派见 core）。"""

from app.adapters.asr.core import (
    AsrHttpError,
    SpeechToTextRequest,
    asr_endpoint,
    parse_business_error,
    speech_to_text,
)

__all__ = [
    "AsrHttpError",
    "SpeechToTextRequest",
    "asr_endpoint",
    "parse_business_error",
    "speech_to_text",
]
