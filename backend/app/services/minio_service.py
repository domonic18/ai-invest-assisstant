"""MinIO object storage service for financial reports and other files."""

import asyncio
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings


class MinIOService:
    """Upload and retrieve files from MinIO."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        # Presigned URLs embed the endpoint host in the signature, so they must
        # be signed with the publicly reachable endpoint rather than the
        # cluster-internal one.  An explicit region keeps presigning purely
        # client-side; otherwise the SDK queries the bucket location over HTTP,
        # which the public endpoint may not be reachable for.
        self._presign_client = (
            Minio(
                settings.minio_public_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
                region=settings.minio_region,
            )
            if settings.minio_public_endpoint
            else self.client
        )
        self.default_bucket = settings.minio_bucket

    async def ensure_bucket(self, bucket_name: str | None = None) -> None:
        """Create the bucket if it does not already exist."""
        bucket = bucket_name or self.default_bucket
        try:
            if not await asyncio.to_thread(self.client.bucket_exists, bucket):
                await asyncio.to_thread(self.client.make_bucket, bucket)
        except S3Error as exc:
            raise RuntimeError(f"Failed to ensure MinIO bucket {bucket}: {exc}") from exc

    async def upload_file(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/pdf",
        bucket_name: str | None = None,
    ) -> str:
        """Upload ``data`` to MinIO and return the object name.

        Args:
            object_name: Destination path inside the bucket.
            data: File bytes.
            content_type: MIME type of the object.
            bucket_name: Optional bucket override.

        Returns:
            The object name that was uploaded.

        Raises:
            RuntimeError: When the upload fails.
        """
        from io import BytesIO

        bucket = bucket_name or self.default_bucket
        await self.ensure_bucket(bucket)
        try:
            await asyncio.to_thread(
                self.client.put_object,
                bucket,
                object_name,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except S3Error as exc:
            raise RuntimeError(f"Failed to upload {object_name}: {exc}") from exc
        return object_name

    async def get_presigned_url(
        self,
        object_name: str,
        bucket_name: str | None = None,
        expires: timedelta = timedelta(days=7),
    ) -> str | None:
        """Return a temporary download URL for an object."""
        bucket = bucket_name or self.default_bucket
        try:
            return await asyncio.to_thread(
                self._presign_client.presigned_get_object,
                bucket,
                object_name,
                expires=expires,
            )
        except S3Error:
            return None

    async def download_file(
        self,
        object_name: str,
        bucket_name: str | None = None,
    ) -> bytes:
        """Download an object and return its bytes."""
        bucket = bucket_name or self.default_bucket
        try:
            response = await asyncio.to_thread(self.client.get_object, bucket, object_name)
            return await asyncio.to_thread(response.read)
        except S3Error as exc:
            raise RuntimeError(f"Failed to download {object_name}: {exc}") from exc


_minio_service: MinIOService | None = None


def get_minio_service() -> MinIOService:
    """Return a lazily initialized MinIO service singleton."""
    global _minio_service
    if _minio_service is None:
        _minio_service = MinIOService()
    return _minio_service
