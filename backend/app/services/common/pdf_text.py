"""PDF 文本抽取（pypdf，尽力而为）。"""

import asyncio

import structlog

logger = structlog.get_logger(__name__)


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
        return "\n".join(parts) if parts else None
    except ImportError:
        logger.debug("pypdf_not_installed_skip_pdf_text")
        return None
    except Exception:  # noqa: BLE001
        logger.warning("pdf_text_extract_failed", exc_info=True)
        return None


async def extract_pdf_text(data: bytes) -> str | None:
    """线程池中从 PDF 抽取可检索文本，失败返回 ``None``。"""
    return await asyncio.to_thread(_extract_pdf_text, data)
