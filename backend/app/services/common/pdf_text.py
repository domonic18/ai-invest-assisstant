"""PDF 文本抽取（pypdf，尽力而为）。"""

import asyncio

import structlog

logger = structlog.get_logger(__name__)


def sanitize_extracted_text(text: str) -> str:
    """剔除写不进 PostgreSQL ``text`` 的字符。

    部分 PDF 的字体缺少 ToUnicode 映射，pypdf 会把字形解成 NUL（000988
    2025 年报摘要实测 59 个）；个别 PDF 还会带出孤立代理字符。两者都会让
    asyncpg 在写 ``file_metadata.content`` 时抛
    ``invalid byte sequence for encoding "UTF8"``，故在抽取边界统一清洗。
    """
    if not text:
        return text
    cleaned = text.replace("\x00", "")
    try:
        cleaned.encode("utf-8")
    except UnicodeEncodeError:
        cleaned = cleaned.encode("utf-8", "replace").decode("utf-8")
    return cleaned


def _extract_pdf_text(data: bytes) -> str | None:
    """尽力从 PDF 提取文本。

    需要安装 ``pypdf``；未安装或解析失败时返回 ``None``，
    调用方可退化为仅存储元数据。
    """
    try:
        from io import BytesIO

        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(BytesIO(data))
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return sanitize_extracted_text("\n".join(parts)) if parts else None
    except ImportError:
        logger.debug("pypdf_not_installed_skip_pdf_text")
        return None
    except Exception:  # noqa: BLE001
        logger.warning("pdf_text_extract_failed", exc_info=True)
        return None


async def extract_pdf_text(data: bytes) -> str | None:
    """线程池中从 PDF 抽取可检索文本，失败返回 ``None``。"""
    return await asyncio.to_thread(_extract_pdf_text, data)
