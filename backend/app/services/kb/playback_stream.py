"""媒体代理流与字幕轨（arch/09 §8，批次 F1）。

视频流必须携带 Range 头（206 分段透传，整文件抓取特征直接 400）；
字幕轨由 ``kb_transcript_segment`` 生成 WebVTT（fetch 同源 Cookie 鉴权）。
凭证校验与异常审计底座在 ``playback_service``。
"""

import asyncio
import mimetypes
import re
from collections.abc import AsyncIterator
from typing import Any, NamedTuple

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KB_PLAYBACK_STREAM_CHUNK_BYTES
from app.core.exceptions import AppError, BadRequestError, NotFoundError
from app.repositories.kb import media_repository
from app.services.common.minio_service import get_minio_service
from app.services.kb.playback_service import _load_media, _record_denial, _require_token

logger = structlog.get_logger(__name__)

_RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeNotSatisfiableError(AppError):
    """Range 头不可满足（越界/无法解析）。"""

    status_code = 416
    default_message = "Range not satisfiable"


class MediaStream(NamedTuple):
    """代理流视图（路由层据此构造 206 StreamingResponse）。"""

    content_type: str
    start: int
    end: int
    total: int
    chunks: AsyncIterator[bytes]


def parse_range_header(header: str | None, total: int) -> tuple[int, int]:
    """解析单区间 Range 头，返回 ``[start, end]``（闭区间，end 已钳到 total-1）。

    Raises:
        BadRequestError: 缺失 Range 头（整文件抓取特征）。
        RangeNotSatisfiableError: 头不可解析或区间越界。
    """
    if not header or not header.strip():
        raise BadRequestError("视频流请求必须携带 Range 头")
    match = _RANGE_PATTERN.match(header.strip())
    if match is None:
        raise RangeNotSatisfiableError("无法解析的 Range 头")
    start_text, end_text = match.groups()
    if start_text == "" and end_text == "":
        raise RangeNotSatisfiableError("空的 Range 区间")
    if start_text == "":
        suffix = min(int(end_text), total)
        start, end = max(0, total - suffix), total - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else total - 1
    if start >= total or start > end:
        raise RangeNotSatisfiableError("Range 区间越界")
    return start, min(end, total - 1)


async def open_media_stream(
    session: AsyncSession,
    *,
    media_id: int,
    token: str,
    range_header: str | None,
    ip: str | None = None,
) -> MediaStream:
    """打开媒体代理流（凭证校验 → Range 解析 → MinIO 区间读）。

    Raises:
        UnauthorizedError: 凭证缺失/过期/错配（含审计）。
        BadRequestError: 缺失 Range 头（含审计）或素材类型不符。
        RangeNotSatisfiableError: Range 不可满足。
        NotFoundError: 素材或对象文件不存在。
        InternalError: Redis / 对象存储不可用。
    """
    payload = await _require_token(
        session, token=token, media_id=media_id, action="stream", ip=ip,
    )
    user_id = int(payload["userId"])
    media = await _load_media(session, media_id, kinds=("video", "audio"))
    minio = get_minio_service()
    stat = await minio.stat_object(media.cos_key)
    if stat is None:
        raise NotFoundError("素材文件不存在或已清理")
    total = stat[0]
    try:
        start, end = parse_range_header(range_header, total)
    except BadRequestError:
        await _record_denial(
            session, user_id=user_id, media_id=media_id, action="stream",
            reason="missing_range_header", ip=ip,
        )
        raise
    except RangeNotSatisfiableError:
        await _record_denial(
            session, user_id=user_id, media_id=media_id, action="stream",
            reason="unsatisfiable_range", ip=ip,
        )
        raise
    content_type = mimetypes.guess_type(media.file_name)[0] or "application/octet-stream"
    response = await minio.open_object_stream(
        media.cos_key, offset=start, length=end - start + 1
    )
    return MediaStream(
        content_type=content_type,
        start=start,
        end=end,
        total=total,
        chunks=_read_blocks(response),
    )


async def _read_blocks(response: Any) -> AsyncIterator[bytes]:
    """分块消费 SDK 区间读响应（64KB 块，结束或中断时释放连接）。"""
    try:
        while True:
            block = await asyncio.to_thread(
                response.read, KB_PLAYBACK_STREAM_CHUNK_BYTES
            )
            if not block:
                break
            yield block
    finally:
        await asyncio.to_thread(response.close)


async def build_subtitle_vtt(
    session: AsyncSession, *, media_id: int
) -> str:
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
