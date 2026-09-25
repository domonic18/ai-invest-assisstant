"""字幕轨生成（arch/09 §8，批次 F1）：文稿分段 → WebVTT。

apiClient Bearer 同源拉取（fetch 可携带 header）；媒体流本身走预签名
直链后，后端不再承担视频字节代理。凭证校验与审计底座在 ``playback_service``。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.kb import media_repository
from app.services.kb.playback_service import _load_media


async def build_subtitle_vtt(session: AsyncSession, *, media_id: int) -> str:
    """由 ``kb_transcript_segment`` 生成 WebVTT 字幕轨（fetch 同源 Cookie 鉴权）。

    Raises:
        BadRequestError: 素材不是课程音视频。
        NotFoundError: 素材不存在。
    """
    media = await _load_media(session, media_id, kinds=("video", "audio"))
    segments = await media_repository.list_segments(session, media.id)
    lines = ["WEBVTT", ""]
    for segment in segments:
        if segment.start_ms is None or segment.end_ms is None:
            continue
        if segment.end_ms <= segment.start_ms:
            continue
        text = (segment.text or "").replace("\n", " ").replace("-->", "→")
        lines.append(
            f"{_ms_to_vtt_timestamp(segment.start_ms)} --> "
            f"{_ms_to_vtt_timestamp(segment.end_ms)}"
        )
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _ms_to_vtt_timestamp(ms: int) -> str:
    """毫秒 → WebVTT 时间戳 ``hh:mm:ss.mmm``。"""
    total_ms = max(0, int(ms))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
