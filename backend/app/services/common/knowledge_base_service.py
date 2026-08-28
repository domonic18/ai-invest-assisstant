"""知识库服务：将研报等文档索引进 Elasticsearch。"""

import asyncio
from datetime import date, datetime
from typing import Any

from elasticsearch import AsyncElasticsearch

from app.core.config import get_settings

DEFAULT_INDEX = "kb-documents"


def _extract_pdf_text(data: bytes) -> str | None:
    """尽力从 PDF 提取文本。

    需要安装 ``pypdf``；未安装时返回 ``None``，调用方可退化为仅索引元数据。
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
    """将文档元数据与内容索引到 Elasticsearch。"""

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
        """关闭由本服务持有的底层 Elasticsearch 客户端。"""
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
        """将文档索引进知识库。

        Args:
            doc_id: 文档唯一标识，通常为 ``source_url`` 哈希。
            stock_code: 关联股票代码（如有关联）。
            title: 文档标题。
            source_url: 原始来源 URL。
            publish_date: 研报发布日期。
            report_type: 规范化后的研报类型（如 ``annual``）。
            file_type: 文件扩展名 / MIME 类别。
            file_size: 文件大小（字节）。
            minio_path: 存储文件在 MinIO 中的对象路径。
            content: 提取出的文本内容（如有）。
            extra: 附加元数据。

        Returns:
            文档索引成功返回 ``True``。
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
        """从文件字节中提取可检索文本。

        当前支持安装了 ``pypdf`` 时的 PDF。
        """
        if file_type.lower() in ("pdf", "application/pdf"):
            return await asyncio.to_thread(_extract_pdf_text, data)
        return None


_kb_service: KnowledgeBaseService | None = None


def get_knowledge_base_service() -> KnowledgeBaseService:
    """返回懒初始化的知识库服务单例。"""
    global _kb_service
    if _kb_service is None:
        _kb_service = KnowledgeBaseService()
    return _kb_service
