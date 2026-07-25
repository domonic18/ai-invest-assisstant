"""Storage orchestration for EastMoney research report PDFs."""

import hashlib
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.file_metadata import FileMetadata
from app.models.news_announcement import NewsAnnouncement
from app.services.minio_service import MinIOService
from collector.core.base import get_engine

logger = structlog.get_logger()

_FILE_CATEGORY = "research_report"


class ResearchReportStore:
    """Save research report metadata to DB and PDFs to MinIO.

    Metadata is always persisted to ``news_announcement`` (upsert by
    ``source_url``) so that reports remain visible even when the PDF download
    failed.  MinIO failures are logged but do not block the database record.
    """

    def __init__(self, minio: MinIOService):
        self.minio = minio

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
                    logger.warning("research_report_store_item_failed", error=msg)
                    errors.append(msg)
            await session.commit()
        return stored, errors

    async def _save_one(
        self,
        session: AsyncSession,
        item: dict[str, Any],
        errors: list[str],
    ) -> None:
        source_url: str = item["source_url"]
        title: str = item["title"]
        stock_code: str = item["stock_code"]
        publish_date: datetime = item["publish_date"]
        extra: dict[str, Any] = dict(item.get("extra") or {})

        result = await session.execute(
            select(NewsAnnouncement).where(
                NewsAnnouncement.source_url == source_url
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.title = title
            row.stock_code = stock_code
            row.publish_date = publish_date
            row.industry_tags = item.get("industry_tags")
            merged = dict(row.extra or {})
            merged.update(extra)
            row.extra = merged
        else:
            row = NewsAnnouncement(
                stock_code=stock_code,
                doc_type="research",
                title=title,
                source="eastmoney",
                source_url=source_url,
                publish_date=publish_date,
                industry_tags=item.get("industry_tags"),
                extra=extra,
            )
            session.add(row)

        file_bytes: bytes | None = item.get("file_bytes")
        info_code = extra.get("info_code")
        if not file_bytes or not info_code:
            await session.flush()
            return

        object_name = (
            f"research-reports/{stock_code}/"
            f"{publish_date.date().isoformat()}_{info_code}.pdf"
        )
        file_size = len(file_bytes)
        md5_hash = hashlib.md5(file_bytes).hexdigest()

        result = await session.execute(
            select(FileMetadata).where(FileMetadata.file_path == object_name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.original_name = title
            existing.broker = extra.get("broker")
            existing.file_size = file_size
            existing.md5_hash = md5_hash
            file_record = existing
        else:
            file_record = FileMetadata(
                file_path=object_name,
                original_name=title,
                file_type=_FILE_CATEGORY,
                stock_code=stock_code,
                report_date=publish_date.date(),
                broker=extra.get("broker"),
                file_size=file_size,
                md5_hash=md5_hash,
            )
            session.add(file_record)

        await session.flush()

        try:
            await self.minio.upload_file(
                object_name=object_name,
                data=file_bytes,
                content_type="application/pdf",
            )
            file_record.download_url = await self.minio.get_presigned_url(object_name)
            merged = dict(row.extra or {})
            merged["file_path"] = object_name
            row.extra = merged
        except Exception as exc:  # noqa: BLE001
            msg = f"MinIO upload failed for {object_name}: {exc}"
            logger.warning("research_report_minio_upload_failed", error=msg)
            errors.append(msg)
