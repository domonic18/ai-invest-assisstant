"""ASR 转写服务：asr_channel_config 配置驱动调用 MiniMax speech_to_text。

转写链路：视频 URL 下载 → ffmpeg 抽音轨（mp3 临时文件即用即删）→ MiniMax。
任一环节失败返回降级原因（不抛异常，调用方落 transcript_status=missing）；
官方接口无热词参数，热词表由情绪判断 prompt 注入纠偏。
"""

from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social import AsrChannelConfig
from app.utils.crypto import decrypt_token

logger = structlog.get_logger(__name__)

_DOWNLOAD_TIMEOUT_SECONDS = 60.0
_ASR_TIMEOUT_SECONDS = 60.0
_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
}


@dataclass(slots=True)
class TranscribeOutcome:
    """转写结果：text 为 None 时 reason 给出降级原因。"""

    text: str | None
    meta: dict[str, Any] | None
    reason: str | None


async def load_config(session: AsyncSession) -> AsrChannelConfig | None:
    """读取单行 ASR 配置。"""
    result = await session.execute(select(AsrChannelConfig).where(AsrChannelConfig.id == 1))
    return result.scalars().first()


async def transcribe_from_url(session: AsyncSession, url: str) -> TranscribeOutcome:
    """下载视频并转写；全程不抛异常，失败给降级原因。

    Args:
        session: 数据库会话（读 ASR 配置）。
        url: 视频 play_addr 地址。

    Returns:
        转写结果（text/meta/reason 三元）。
    """
    config = await load_config(session)
    if config is None or not config.enabled:
        return TranscribeOutcome(None, None, "asr_disabled")
    if not config.api_key_encrypted:
        return TranscribeOutcome(None, None, "asr_not_configured")
    try:
        api_key = decrypt_token(config.api_key_encrypted)
    except Exception:  # noqa: BLE001 —— 密钥解密失败按未配置降级
        return TranscribeOutcome(None, None, "asr_key_invalid")

    audio_bytes = await _download(url)
    if audio_bytes is None:
        return TranscribeOutcome(None, None, "audio_download_failed")
    mp3 = await _extract_audio(audio_bytes)
    if mp3 is None:
        return TranscribeOutcome(None, None, "ffmpeg_unavailable")

    text = await _call_minimax(config, api_key, mp3)
    if text is None:
        return TranscribeOutcome(None, None, "asr_request_failed")
    return TranscribeOutcome(
        text,
        {
            "provider": config.provider,
            "model": config.model,
            "char_count": len(text),
        },
        None,
    )


async def _download(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(
            headers=_DOWNLOAD_HEADERS,
            timeout=_DOWNLOAD_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("social_asr_download_failed", url=url, error=str(exc))
        return None


async def _extract_audio(video_bytes: bytes) -> bytes | None:
    """ffmpeg 抽音轨为 16k 单声道 mp3；ffmpeg 不可用或失败返回 None。"""
    import asyncio
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="social-asr-") as tmp:
        input_path = Path(tmp) / "input.mp4"
        output_path = Path(tmp) / "audio.mp3"
        input_path.write_bytes(video_bytes)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(output_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await proc.wait()
        except FileNotFoundError:
            logger.warning("social_asr_ffmpeg_missing")
            return None
        if returncode != 0 or not output_path.exists():
            return None
        return output_path.read_bytes()


async def _call_minimax(config: AsrChannelConfig, api_key: str, mp3: bytes) -> str | None:
    """调用 MiniMax speech_to_text，返回转写文本。"""
    base_url = (config.base_url or "").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=_ASR_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url}/v1/speech_to_text",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": config.model, "response_format": "json"},
                files={"file": ("audio.mp3", mp3, "audio/mpeg")},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("social_asr_request_failed", error=str(exc))
        return None
    text = payload.get("text")
    return text if isinstance(text, str) and text.strip() else None
