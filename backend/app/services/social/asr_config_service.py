"""ASR 渠道配置服务（asr_channel_config 单行表，管理端「社媒追踪」维护）。

密钥 write-only：更新请求 apiKey 为 None/空串保留原值，传入即换（Fernet 落库
+ masked 回显）；连接测试用内置正弦波样例音频实调官方接口（~1s，即生成即用）。
"""

import io
import math
import struct
import time
import wave
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social import AsrChannelConfig
from app.schemas.social import (
    AsrConfigResponse,
    AsrConfigTestResponse,
    AsrConfigUpdateRequest,
)
from app.services.admin.audit_service import record_audit
from app.utils.api_base import normalize_asr_base
from app.utils.crypto import encrypt_token, mask_token

logger = structlog.get_logger(__name__)

AUDIT_ASR_CONFIG_UPDATE = "social.asr_config.update"
AUDIT_ASR_CONFIG_TEST = "social.asr_config.test"

#: 连接测试样例音频：1 秒 440Hz 16k 单声道 16bit WAV
_TEST_AUDIO_SECONDS = 1.0
_TEST_AUDIO_RATE = 16000
_TEST_TIMEOUT_SECONDS = 30.0


async def get_or_create_config(session: AsyncSession) -> AsrChannelConfig:
    """读单行配置；首次访问落默认行（provider/base_url/model 走模型默认）。"""
    config = await session.get(AsrChannelConfig, 1)
    if config is None:
        config = AsrChannelConfig(id=1)
        session.add(config)
        await session.commit()
        await session.refresh(config)
    return config


def to_response(config: AsrChannelConfig) -> AsrConfigResponse:
    """masked 视图（密钥只回脱敏串与是否已配置）。"""
    return AsrConfigResponse(
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        api_key_masked=config.api_key_masked,
        api_key_configured=bool(config.api_key_encrypted),
        max_audio_seconds=config.max_audio_seconds,
        hotwords=list(config.hotwords),
        enabled=config.enabled,
        updated_at=config.updated_at,
    )


async def update_config(
    session: AsyncSession, payload: AsrConfigUpdateRequest, *, actor_id: int
) -> AsrConfigResponse:
    """更新配置（apiKey write-only：None/空串保留原值；写审计）。"""
    config = await get_or_create_config(session)
    fields = payload.model_dump(exclude_unset=True)
    api_key = fields.pop("api_key", None)
    for key, value in fields.items():
        setattr(config, key, value)
    if api_key:
        config.api_key_encrypted = encrypt_token(api_key)
        config.api_key_masked = mask_token(api_key)
    config.updated_by = actor_id
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_ASR_CONFIG_UPDATE,
        detail={"enabled": config.enabled, "model": config.model, "apiKeyChanged": bool(api_key)},
    )
    await session.commit()
    await session.refresh(config)
    return to_response(config)


async def test_connection(
    session: AsyncSession, *, actor_id: int
) -> AsrConfigTestResponse:
    """连接测试：以当前保存配置（解密密钥）实调转写接口，返回耗时与文本。

    成功判据是「HTTP 2xx 且无 base_resp 业务错误」而非转写文本非空——样例音频
    为无人声正弦波，接口正常时合规返回空文本（2026-09-15 走查误报教训）。
    """
    from app.services.social.asr_service import minimax_business_error
    from app.utils.crypto import decrypt_token

    config = await get_or_create_config(session)
    started = time.monotonic()
    error: str | None = None
    text: str | None = None

    if not config.api_key_encrypted:
        error = "API Key 未配置"
    else:
        try:
            api_key = decrypt_token(config.api_key_encrypted)
            payload = await _transcribe_sample(config, api_key)
            error = minimax_business_error(payload)
            if error is None:
                text = (payload.get("text") or "").strip() or None
        except Exception as exc:  # noqa: BLE001 —— 测试不抛异常，失败给原因
            error = str(exc)

    latency_ms = int((time.monotonic() - started) * 1000)
    ok = error is None
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_ASR_CONFIG_TEST,
        detail={"ok": ok, "latencyMs": latency_ms},
    )
    await session.commit()
    if not ok:
        logger.warning("social_asr_config_test_failed", error=error, latency_ms=latency_ms)
    return AsrConfigTestResponse(ok=ok, latency_ms=latency_ms, text=text, error=error)


async def _transcribe_sample(config: AsrChannelConfig, api_key: str) -> dict[str, Any]:
    """内置样例音频实调 speech_to_text，返回原始 JSON 响应（异常向上传播）。"""
    base_url = normalize_asr_base(config.base_url or "")
    audio = _generate_sample_wav()
    async with httpx.AsyncClient(timeout=_TEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{base_url}/v1/speech_to_text",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": config.model, "response_format": "json"},
            files={"file": ("sample.wav", audio, "audio/wav")},
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
    return payload


def _generate_sample_wav() -> bytes:
    """1 秒 440Hz 正弦波 WAV（16k 单声道 16bit），连接测试即用即弃。"""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_TEST_AUDIO_RATE)
        frames = bytearray()
        for i in range(int(_TEST_AUDIO_RATE * _TEST_AUDIO_SECONDS)):
            value = int(0.3 * 32767 * math.sin(2 * math.pi * 440 * i / _TEST_AUDIO_RATE))
            frames += struct.pack("<h", value)
        wav.writeframes(bytes(frames))
    return buffer.getvalue()
