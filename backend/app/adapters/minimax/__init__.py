"""MiniMax 开放平台适配层：speech_to_text 转写的共享 HTTP 核心。"""

from app.adapters.minimax.asr import (
    MiniMaxAsrHttpError,
    SpeechToTextRequest,
    parse_business_error,
    speech_to_text,
)

__all__ = [
    "MiniMaxAsrHttpError",
    "SpeechToTextRequest",
    "parse_business_error",
    "speech_to_text",
]
