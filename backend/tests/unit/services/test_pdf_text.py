"""PDF 文本抽取清洗单测（NUL 与孤立代理字符）。"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.common.pdf_text import extract_pdf_text, sanitize_extracted_text


@pytest.mark.unit
class TestSanitizeExtractedText:
    def test_removes_nul_bytes(self) -> None:
        assert sanitize_extracted_text("2025 年报\x00摘要") == "2025 年报摘要"

    def test_replaces_lone_surrogates(self) -> None:
        assert sanitize_extracted_text("好\ud800坏") == "好?坏"

    def test_keeps_normal_text(self) -> None:
        text = "2025 年年度报告\n\t营业收入 1,234.56 元"
        assert sanitize_extracted_text(text) == text

    def test_empty_text(self) -> None:
        assert sanitize_extracted_text("") == ""


@pytest.mark.unit
class TestExtractPdfText:
    @pytest.mark.asyncio
    async def test_extracted_text_is_sanitized(self) -> None:
        """抽取出的 NUL 必须被清洗，否则写库必被 PostgreSQL 拒绝。"""
        page = MagicMock()
        page.extract_text.return_value = "摘要\x00正文"
        reader = MagicMock()
        reader.pages = [page]

        with patch("pypdf.PdfReader", return_value=reader):
            text = await extract_pdf_text(b"%PDF-1.4")

        assert text == "摘要正文"
