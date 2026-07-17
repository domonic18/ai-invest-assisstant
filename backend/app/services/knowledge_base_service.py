"""Knowledge base service for indexing financial reports and other documents."""

from datetime import date, datetime
from typing import Any

from elasticsearch import AsyncElasticsearch

from app.core.config import get_settings

DEFAULT_INDEX = "kb-documents"


def _extract_pdf_text(data: bytes) -> str | None:
    """Best-effort text extraction from a PDF.

    Requires ``pypdf`` to be installed; returns ``None`` otherwise so callers can
    fall back to metadata-only indexing.
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
    except Exception:  # noqa: BLE001
        return None


class KnowledgeBaseService:
    """Index document metadata and content to Elasticsearch."""

    def __init__(self, client: AsyncElasticsearch | None = None) -> None:
        self.client = client
        self._owns_client = client is None
        self.index_name = DEFAULT_INDEX

    async def _get_client(self) -> AsyncElasticsearch:
        if self.client is None:
            settings = get_settings()
            self.client = AsyncElasticsearch(settings.elasticsearch_url)
        return self.client

    async def close(self) -> None:
        """Close the underlying Elasticsearch client if this service owns it."""
        if self._owns_client and self.client is not None:
            await self.client.close()
            self.client = None

    async def index_document(
        self,
        doc_id: str,
        stock_code: str | None,
        title: str,
        source_url: str,
        publish_date: date | datetime | None,
        report_type: str | None,
        file_type: str,
        file_size: int,
        minio_path: str,
        content: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        """Index a document into the knowledge base.

        Args:
            doc_id: Unique document identifier, typically ``source_url`` hash.
            stock_code: Related stock code, if any.
            title: Document title.
            source_url: Original source URL.
            publish_date: Report publication date.
            report_type: Normalized report type (e.g. ``annual``).
            file_type: File extension / MIME category.
            file_size: File size in bytes.
            minio_path: MinIO object path for the stored file.
            content: Extracted text content, if available.
            extra: Additional metadata.

        Returns:
            ``True`` if the document was indexed successfully.
        """
        body: dict[str, Any] = {
            "stock_code": stock_code,
            "title": title,
            "source_url": source_url,
            "publish_date": publish_date.isoformat() if publish_date else None,
            "report_type": report_type,
            "file_type": file_type,
            "file_size": file_size,
            "minio_path": minio_path,
            "content": content,
            "extra": extra or {},
            "indexed_at": datetime.utcnow().isoformat(),
        }
        try:
            client = await self._get_client()
            await client.index(index=self.index_name, id=doc_id, document=body)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def extract_text(self, data: bytes, file_type: str) -> str | None:
        """Extract searchable text from file bytes.

        Currently supports PDFs when ``pypdf`` is installed.
        """
        if file_type.lower() in ("pdf", "application/pdf"):
            return _extract_pdf_text(data)
        return None


_kb_service: KnowledgeBaseService | None = None


def get_knowledge_base_service() -> KnowledgeBaseService:
    """Return a lazily initialized knowledge base service singleton."""
    global _kb_service
    if _kb_service is None:
        _kb_service = KnowledgeBaseService()
    return _kb_service
