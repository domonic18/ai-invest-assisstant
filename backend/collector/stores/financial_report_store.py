"""Storage orchestration for downloaded financial report PDFs."""

import hashlib
from datetime import date
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.file_metadata import FileMetadata
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.minio_service import MinIOService
from collector.core.base import get_engine

logger = structlog.get_logger()

_FILE_CATEGORY = "financial_report"


class FinancialReportStore:
    """Save financial report PDFs to MinIO, metadata to DB, and index to KB.

    Storage is resilient: metadata is always persisted to PostgreSQL first so that
    administrators can see what was collected.  MinIO and knowledge-base failures
    are logged but do not block the database record.
    """

    def __init__(
        self,
        minio: MinIOService,
        kb: KnowledgeBaseService,
    ):
        self.minio = minio
        self.kb = kb

    async def save_many(self, items: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Persist all items and return the number saved plus any error messages."""
        session_maker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
        stored = 0
        errors: list[str] = []
        async with session_maker() as session:
            for item in items:
                try:
                    async with session.begin_nested():
                        await self._save_one(session, item, errors)
                    stored += 1
                except Exception as exc:  # noqa: BLE001
                    msg = f"{item.get('stock_code')} {item.get('title')}: {exc}"
                    logger.warning("financial_report_store_item_failed", error=msg)
                    errors.append(msg)
            await session.commit()
        await self.kb.close()
        return stored, errors

    async def _save_one(
        self,
        session: AsyncSession,
        item: dict[str, Any],
        errors: list[str],
    ) -> None:
        stock_code: str = item["stock_code"]
        publish_date: date = item["publish_date"]
        report_type: str = item["report_type"]
        file_bytes: bytes = item["file_bytes"]
        source_url: str = item["source_url"]
        title: str = item["title"]

        file_ext = item.get("file_type") or "pdf"
        file_size = len(file_bytes)
        md5_hash = hashlib.md5(file_bytes).hexdigest()
        object_name = self._object_name(stock_code, publish_date, report_type, file_ext)

        from sqlalchemy import select

        result = await session.execute(
            select(FileMetadata).where(FileMetadata.file_path == object_name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.original_name = title
            existing.file_type = _FILE_CATEGORY
            existing.report_date = publish_date
            existing.report_type = report_type
            existing.file_size = file_size
            existing.md5_hash = md5_hash
            file_record = existing
        else:
            file_record = FileMetadata(
                file_path=object_name,
                original_name=title,
                file_type=_FILE_CATEGORY,
                stock_code=stock_code,
                report_date=publish_date,
                report_type=report_type,
                file_size=file_size,
                md5_hash=md5_hash,
            )
            session.add(file_record)

        await session.flush()
        await session.refresh(file_record)

        try:
            await self.minio.upload_file(
                object_name=object_name,
                data=file_bytes,
                content_type="application/pdf",
            )
            presigned_url = await self.minio.get_presigned_url(object_name)
            file_record.download_url = presigned_url
        except Exception as exc:  # noqa: BLE001
            msg = f"MinIO upload failed for {object_name}: {exc}"
            logger.warning("financial_report_minio_upload_failed", error=msg)
            errors.append(msg)

        try:
            doc_id = hashlib.sha256(source_url.encode()).hexdigest()
            content = await self.kb.extract_text(file_bytes, file_ext)
            await self.kb.index_document(
                doc_id=doc_id,
                stock_code=stock_code,
                title=title,
                source_url=source_url,
                publish_date=publish_date,
                report_type=report_type,
                file_type=file_ext,
                file_size=file_size,
                minio_path=object_name,
                content=content,
                extra={
                    "file_metadata_id": file_record.id,
                    "announcement_id": item.get("announcement_id"),
                    "org_id": item.get("org_id"),
                },
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"Knowledge base indexing failed for {object_name}: {exc}"
            logger.warning("financial_report_kb_index_failed", error=msg)
            errors.append(msg)

    def _object_name(
        self,
        stock_code: str,
        publish_date: date,
        report_type: str,
        file_ext: str,
    ) -> str:
        return (
            f"financial-reports/{stock_code}/"
            f"{publish_date.isoformat()}_{report_type}.{file_ext.lower()}"
        )
