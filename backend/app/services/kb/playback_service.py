"""播放凭证、媒体代理流、书页水印与字幕轨（arch/12 §8，批次 F1）。

防盗分层：一次性短时效凭证（Redis ≤30min，绑定用户+素材）→ 视频流必须
携带 Range 头（206 分段透传，整文件抓取特征直接 400）→ 书页服务端烧录
「用户名+日期」水印（干净页缓存与水印合成解耦）。异常拉取全量审计
``kb.security.denied`` 并按账号滑动窗口计数（阈值告警日志；管理端
告警展示归批次 G）。
"""

import asyncio
import json
import mimetypes
import re
import secrets
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator
from datetime import timedelta
from io import BytesIO
from typing import Any, NamedTuple

import structlog
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_BOOK_PAGE_CACHE_PAGES,
    KB_BOOK_PDF_CACHE_FILES,
    KB_BOOK_RENDER_SCALE,
    KB_IMAGE_ORIGINAL_URL_TTL_SECONDS,
    KB_PLAYBACK_STREAM_CHUNK_BYTES,
    KB_PLAYBACK_TOKEN_KEY_TEMPLATE,
    KB_PLAYBACK_TOKEN_TTL_SECONDS,
    KB_SECURITY_ALERT_THRESHOLD,
    KB_SECURITY_DENIED_KEY_TEMPLATE,
    KB_SECURITY_DENIED_WINDOW_SECONDS,
    KbProcessStatus,
)
from app.core.cache import get_redis
from app.core.clock import today_cn
from app.core.exceptions import (
    AppError,
    BadRequestError,
    InternalError,
    NotFoundError,
    UnauthorizedError,
)
from app.models.kb import KbImageAsset, KbMedia, KbSource
from app.models.user import User
from app.repositories.kb import media_repository
from app.schemas.kb import KbImageUrlResponse, KbPlaybackTokenResponse
from app.services.admin.audit_service import record_audit
from app.services.common.minio_service import get_minio_service

logger = structlog.get_logger(__name__)

_AUDIT_ACTION_DENIED = "kb.security.denied"
_RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")

#: 水印 CJK 字体候选（容器 apt 装字体；macOS 候选供本地开发）
_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
)


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


class _LruCache:
    """定容量 LRU（书页/PDF 字节缓存，仅事件循环内访问故无锁）。"""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._data: OrderedDict[Any, Any] = OrderedDict()

    def get(self, key: Any) -> Any | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: Any, value: Any) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


_PDF_CACHE = _LruCache(KB_BOOK_PDF_CACHE_FILES)
_PAGE_CACHE = _LruCache(KB_BOOK_PAGE_CACHE_PAGES)


# ---------------------------------------------------------------------------
# 凭证
# ---------------------------------------------------------------------------


async def issue_playback_token(
    session: AsyncSession, *, user_id: int, media_id: int
) -> KbPlaybackTokenResponse:
    """签发播放凭证（≤30min 绑定用户+素材，TTL 内多次 Range 复用；携带上/下一集 id）。

    凭证值带 ``{userId}.`` 前缀：stream/书页端点无 Bearer 上下文（元素 src
    无法携带 header），过期/泄露凭证的审计归属靠前缀恢复。

    Args:
        session: 数据库会话。
        user_id: 请求用户 id。
        media_id: 素材 id（课程集或书）。

    Returns:
        凭证视图（token/expiresIn/prevMediaId/nextMediaId）。

    Raises:
        NotFoundError: 素材不存在/未完成处理/知识库停用。
        InternalError: Redis 不可用（安全凭证 fail-closed）。
    """
    media = await _load_media(session, media_id)
    token = f"{user_id}.{secrets.token_urlsafe(32)}"
    payload = json.dumps({"userId": user_id, "mediaId": media_id})
    try:
        await get_redis().set(
            KB_PLAYBACK_TOKEN_KEY_TEMPLATE.format(token=token),
            payload,
            ex=KB_PLAYBACK_TOKEN_TTL_SECONDS,
        )
    except Exception as exc:  # RedisError
        logger.error("kb_playback_redis_unavailable", error=str(exc))
        raise InternalError("播放凭证服务暂不可用，请稍后重试") from exc

    prev_id, next_id = (None, None)
    if media.media_kind in ("video", "audio"):
        prev_id, next_id = await _neighbor_episode_ids(session, media)
    return KbPlaybackTokenResponse(
        token=token,
        expires_in=KB_PLAYBACK_TOKEN_TTL_SECONDS,
        media_id=media_id,
        prev_media_id=prev_id,
        next_media_id=next_id,
        page_count=media.page_count if media.media_kind == "book" else None,
    )


async def _neighbor_episode_ids(
    session: AsyncSession, media: KbMedia
) -> tuple[int | None, int | None]:
    """同知识库可播集序列中当前集的相邻集 id（书素材返回 None 对）。"""
    siblings = await media_repository.list_by_source(session, media.source_id)
    playable = [
        m.id
        for m in siblings
        if m.media_kind in ("video", "audio") and m.process_status == KbProcessStatus.DONE
    ]
    if media.id not in playable:
        return None, None
    index = playable.index(media.id)
    prev_id = playable[index - 1] if index > 0 else None
    next_id = playable[index + 1] if index + 1 < len(playable) else None
    return prev_id, next_id


def _token_user_hint(token: str) -> int | None:
    """从凭证 ``{userId}.`` 前缀解析归属用户（不可解析返回 None）。"""
    head = token.split(".", 1)[0]
    return int(head) if head.isdigit() else None


async def _require_token(
    session: AsyncSession,
    *,
    token: str,
    media_id: int,
    action: str,
    ip: str | None,
) -> dict[str, Any]:
    """校验播放凭证并返回 Redis 载荷（过期/素材错配 → 401 + 审计）。

    stream/书页端点无 Bearer 上下文（``<video>``/``<img>`` src 无法携带
    header），凭证本身即身份：归属用户由凭证前缀与载荷恢复。
    """
    try:
        raw = await get_redis().get(
            KB_PLAYBACK_TOKEN_KEY_TEMPLATE.format(token=token)
        )
    except Exception as exc:  # RedisError
        logger.error("kb_playback_redis_unavailable", error=str(exc))
        raise InternalError("播放凭证服务暂不可用，请稍后重试") from exc
    if raw is None:
        await _record_denial(
            session, user_id=_token_user_hint(token), media_id=media_id, action=action,
            reason="expired_or_unknown_token", ip=ip,
        )
        raise UnauthorizedError("播放凭证无效或已过期")
    try:
        payload: dict[str, Any] = json.loads(raw)
    except (TypeError, ValueError):
        await _record_denial(
            session, user_id=_token_user_hint(token), media_id=media_id, action=action,
            reason="malformed_token", ip=ip,
        )
        raise UnauthorizedError("播放凭证无效")
    if payload.get("mediaId") != media_id:
        await _record_denial(
            session, user_id=payload.get("userId"), media_id=media_id, action=action,
            reason="media_mismatch", ip=ip,
        )
        raise UnauthorizedError("播放凭证与请求素材不匹配")
    return payload


async def _record_denial(
    session: AsyncSession,
    *,
    user_id: int | None,
    media_id: int,
    action: str,
    reason: str,
    ip: str | None,
) -> None:
    """审计 ``kb.security.denied`` 并维护账号级滑动窗口计数。

    无法归属账号的异常（凭证完全不可解析，或归属指向不存在的账号——
    凭证前缀是外部输入不可信，伪造前缀不得触发审计表 FK 违约）仅留
    结构化日志：审计表 ``actor_id`` 非空约束不允许无主记录。
    """
    if user_id is None or await session.get(User, user_id) is None:
        logger.warning(
            "kb_security_denial_unattributed",
            action=action,
            reason=reason,
            media_id=media_id,
            ip=ip,
        )
        return
    count = await _bump_denial_count(user_id)
    detail: dict[str, Any] = {
        "action": action,
        "reason": reason,
        "mediaId": media_id,
    }
    if count >= KB_SECURITY_ALERT_THRESHOLD:
        detail["alert"] = True
        logger.warning(
            "kb_security_denial_threshold",
            user_id=user_id,
            count=count,
            window_seconds=KB_SECURITY_DENIED_WINDOW_SECONDS,
        )
    await record_audit(
        session,
        actor_id=user_id,
        action=_AUDIT_ACTION_DENIED,
        target_user_id=user_id,
        detail=detail,
        ip=ip,
    )
    await session.commit()


async def _bump_denial_count(user_id: int) -> int:
    """滑动窗口计数 +1 并返回窗口内当前次数（Redis 故障返回 0 不阻塞审计）。"""
    try:
        client = get_redis()
        key = KB_SECURITY_DENIED_KEY_TEMPLATE.format(user_id=user_id)
        now = time.time()
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        async with client.pipeline(transaction=False) as pipe:
            pipe.zadd(key, {member: now})
            pipe.zremrangebyscore(
                key, 0, now - KB_SECURITY_DENIED_WINDOW_SECONDS
            )
            pipe.expire(key, KB_SECURITY_DENIED_WINDOW_SECONDS * 2)
            pipe.zcard(key)
            results = await pipe.execute()
        return int(results[-1])
    except Exception as exc:  # RedisError
        logger.warning("kb_security_count_unavailable", error=str(exc))
        return 0


async def issue_image_url(
    session: AsyncSession, *, image_id: int
) -> KbImageUrlResponse:
    """签发图片原图短时效预签名 URL（≤15min；消费侧点击原图时按需签）。

    Args:
        session: 数据库会话。
        image_id: 图片资产 id（kb_image_asset）。

    Returns:
        预签名 URL 视图（url/expiresIn）。

    Raises:
        NotFoundError: 资产不存在或所属素材不可消费。
        InternalError: 对象存储不可用。
    """
    asset = await session.get(KbImageAsset, image_id)
    if asset is None:
        raise NotFoundError("图片不存在")
    await _load_media(session, asset.media_id)
    url = await get_minio_service().get_presigned_url(
        asset.cos_key, expires=timedelta(seconds=KB_IMAGE_ORIGINAL_URL_TTL_SECONDS)
    )
    if url is None:
        raise InternalError("对象存储暂不可用，请稍后重试")
    return KbImageUrlResponse(
        url=url, expires_in=KB_IMAGE_ORIGINAL_URL_TTL_SECONDS
    )


# ---------------------------------------------------------------------------
# 素材加载与视频代理流
# ---------------------------------------------------------------------------


async def _load_media(
    session: AsyncSession,
    media_id: int,
    *,
    kinds: tuple[str, ...] | None = None,
) -> KbMedia:
    """加载可消费素材（存活 + 所属库启用 + 处理完成；不满足按 404 隐藏）。"""
    media = await media_repository.get(session, media_id)
    if media is None or media.deleted_at is not None:
        raise NotFoundError("素材不存在")
    source = await session.get(KbSource, media.source_id)
    if (
        source is None
        or source.deleted_at is not None
        or not source.enabled
    ):
        raise NotFoundError("素材不存在")
    if media.process_status != KbProcessStatus.DONE:
        raise NotFoundError("素材暂不可用")
    if kinds is not None and media.media_kind not in kinds:
        raise BadRequestError("素材类型不支持该操作")
    return media


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


# ---------------------------------------------------------------------------
# 书页渲染与水印
# ---------------------------------------------------------------------------


async def render_book_page(
    session: AsyncSession,
    *,
    media_id: int,
    page_no: int,
    token: str,
    ip: str | None = None,
) -> bytes:
    """渲染书页位图并烧录「用户名+日期」水印，返回 PNG 字节。

    凭证即身份（元素 src 无 Bearer）：水印用户名按凭证载荷 userId 回查。
    干净页（未加水印）按 (mediaId, pageNo) LRU 缓存，与每请求的水印
    合成解耦；PDF 字节单独 LRU（容量更小，控制内存上界）。

    Raises:
        UnauthorizedError: 凭证缺失/过期/错配（含审计）或用户已不可用。
        BadRequestError: 素材不是书。
        NotFoundError: 素材/页码越界/对象文件不存在。
    """
    payload = await _require_token(
        session, token=token, media_id=media_id, action="book_page", ip=ip,
    )
    user = await session.get(User, int(payload["userId"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("播放凭证归属用户已不可用")
    media = await _load_media(session, media_id, kinds=("book",))
    cache_key = (media.id, page_no)
    clean_png: bytes | None = _PAGE_CACHE.get(cache_key)
    if clean_png is None:
        pdf_bytes: bytes | None = _PDF_CACHE.get(media.id)
        if pdf_bytes is None:
            pdf_bytes = await get_minio_service().download_file(media.cos_key)
            _PDF_CACHE.put(media.id, pdf_bytes)
        clean_png = await asyncio.to_thread(
            _render_clean_page, pdf_bytes, page_no
        )
        _PAGE_CACHE.put(cache_key, clean_png)
    label = f"{user.username} {today_cn().strftime('%Y-%m-%d')}"
    return await asyncio.to_thread(_composite_watermark, clean_png, label)


def _render_clean_page(pdf_bytes: bytes, page_no: int) -> bytes:
    """pypdfium2 渲染单页为干净 PNG（144 DPI，无水印）。"""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        if page_no < 1 or page_no > len(doc):
            raise NotFoundError("页码超出范围")
        page = doc[page_no - 1]
        try:
            bitmap = page.render(scale=KB_BOOK_RENDER_SCALE)
            image = bitmap.to_pil()
        finally:
            page.close()
    finally:
        doc.close()
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _resolve_font_path() -> str | None:
    """返回首个存在的水印字体路径（CJK 候选缺失时 None，退化位图字体）。"""
    import os

    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _composite_watermark(png_bytes: bytes, label: str) -> bytes:
    """干净页上叠平铺斜排水印（用户名+日期），返回 PNG 字节。"""
    font_path = _resolve_font_path()
    with Image.open(BytesIO(png_bytes)) as image:
        width, height = image.size
        font_size = max(18, width // 24)
        if font_path is not None:
            font: ImageFont.FreeTypeFont | ImageFont.ImageFont = (
                ImageFont.truetype(font_path, font_size)
            )
        else:
            logger.warning("kb_watermark_font_missing", candidates=_FONT_CANDIDATES)
            font = ImageFont.load_default()
        diagonal = int((width * width + height * height) ** 0.5) + font_size * 2
        overlay = Image.new("RGBA", (diagonal, diagonal), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w, text_h = int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])
        gap_x, gap_y = text_w + font_size * 4, text_h + font_size * 6
        y = 0
        while y < diagonal:
            x = -text_w
            while x < diagonal:
                draw.text((x, y), label, font=font, fill=(160, 160, 160, 52))
                x += gap_x
            y += gap_y
        overlay = overlay.rotate(30, resample=Image.Resampling.BICUBIC)
        left, top = (diagonal - width) // 2, (diagonal - height) // 2
        overlay = overlay.crop((left, top, left + width, top + height))
        base = image.convert("RGBA")
        base.alpha_composite(overlay)
        buffer = BytesIO()
        base.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()


# ---------------------------------------------------------------------------
# 字幕轨
# ---------------------------------------------------------------------------


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
