"""书页渲染与「用户名+日期」水印烧录（arch/12 §8，批次 F1）。

干净页（未加水印）按 (mediaId, pageNo) LRU 缓存，与每请求的水印合成
解耦；PDF 字节单独 LRU（容量更小，控制内存上界）。凭证校验底座在
``playback_service``。
"""

import asyncio
from collections import OrderedDict
from io import BytesIO
from typing import Any

import structlog
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_BOOK_PAGE_CACHE_PAGES,
    KB_BOOK_PDF_CACHE_FILES,
    KB_BOOK_RENDER_SCALE,
)
from app.core.clock import today_cn
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.models.user import User
from app.services.common.minio_service import get_minio_service
from app.services.kb.playback_service import _load_media, _require_token

logger = structlog.get_logger(__name__)

#: 水印 CJK 字体候选（容器 apt 装字体；macOS 候选供本地开发）
_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
)


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
