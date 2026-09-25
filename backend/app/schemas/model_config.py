"""管理后台模型配置 API schema（ASR 渠道部分；LLM 条目见 llm_config.py）。"""

from datetime import datetime

from app.schemas.base import CamelModel


class AsrConfigResponse(CamelModel):
    """GET /admin/model-configs/asr 响应（masked 视图，密钥只回脱敏串）。"""

    provider: str
    base_url: str
    model: str
    api_key_masked: str | None = None
    api_key_configured: bool
    max_audio_seconds: int
    hotwords: list[str]
    enabled: bool
    updated_at: datetime


class AsrConfigUpdateRequest(CamelModel):
    """PUT /admin/model-configs/asr 请求（apiKey write-only：None/空串=保留原值）。"""

    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_audio_seconds: int | None = None
    hotwords: list[str] | None = None
    enabled: bool | None = None


class AsrConfigTestResponse(CamelModel):
    """POST /admin/model-configs/asr/test 响应：连接测试结果。"""

    ok: bool
    latency_ms: int
    text: str | None = None
    error: str | None = None
