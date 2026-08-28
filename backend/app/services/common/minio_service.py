"""MinIO 对象存储服务：存储研报等文件。"""

import asyncio
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings


class MinIOService:
    """MinIO 文件上传与获取。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        # 预签名 URL 会把 endpoint 主机写入签名，因此必须用公网可达的
        # endpoint 而非集群内部地址来签名。显式指定 region 可让预签名
        # 纯客户端完成；否则 SDK 会通过 HTTP 查询 bucket 所在区域，
        # 而公网 endpoint 可能无法访问该查询接口。
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
        """若 bucket 不存在则创建。"""
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
        """上传 ``data`` 到 MinIO 并返回对象名。

        Args:
            object_name: bucket 内的目标路径。
            data: 文件字节内容。
            content_type: 对象的 MIME 类型。
            bucket_name: 可选的 bucket 覆盖。

        Returns:
            已上传的对象名。

        Raises:
            RuntimeError: 上传失败时抛出。
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
        """返回对象的临时下载 URL。"""
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
        """下载对象并返回其字节内容。"""
        bucket = bucket_name or self.default_bucket
        try:
            response = await asyncio.to_thread(self.client.get_object, bucket, object_name)
            return await asyncio.to_thread(response.read)
        except S3Error as exc:
            raise RuntimeError(f"Failed to download {object_name}: {exc}") from exc


_minio_service: MinIOService | None = None


def get_minio_service() -> MinIOService:
    """返回懒初始化的 MinIO 服务单例。"""
    global _minio_service
    if _minio_service is None:
        _minio_service = MinIOService()
    return _minio_service
