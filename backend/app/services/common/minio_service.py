"""MinIO 对象存储服务：存储研报等文件。"""

import asyncio
from datetime import timedelta
from typing import NamedTuple

import structlog
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class MultipartPart(NamedTuple):
    """已上传分片信息（etag 已去引号小写）。"""

    part_number: int
    etag: str
    size: int


class MultipartSessionNotFoundError(RuntimeError):
    """uploadId 不存在（已 complete/abort 或过期）。"""



class MinIOService:
    """MinIO 文件上传与获取。"""

    def __init__(self) -> None:
        settings = get_settings()

        def build_client(endpoint: str) -> Minio:
            # COS 等非 us-east-1 的 S3 兼容服务需要显式 region，否则签名被拒；
            # COS 还禁用 path-style 寻址，须启用 virtual-host（SDK 自动把
            # bucket 前置到主机名，因此 endpoint 用区域域名而非 bucket 域名）。
            client = Minio(
                endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
                region=settings.minio_region,
            )
            if settings.minio_virtual_host:
                client.enable_virtual_style_endpoint()
            return client

        self.client = build_client(settings.minio_endpoint)
        # 预签名 URL 会把 endpoint 主机写入签名，必须用公网可达的 endpoint
        # 而非集群内部地址来签名
        self._presign_client = (
            build_client(settings.minio_public_endpoint)
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
        """返回对象的临时下载 URL。

        签名内携带 ``response-content-disposition: inline``，浏览器拿到
        application/pdf 时内联打开而非触发下载。
        """
        bucket = bucket_name or self.default_bucket
        try:
            return await asyncio.to_thread(
                self._presign_client.presigned_get_object,
                bucket,
                object_name,
                expires=expires,
                response_headers={"response-content-disposition": "inline"},
            )
        except S3Error:
            return None

    async def presigned_put_url(
        self,
        object_name: str,
        bucket_name: str | None = None,
        expires: timedelta = timedelta(hours=6),
    ) -> str:
        """返回对象的预签名直传 URL（浏览器 PUT，不经后端中转）。"""
        bucket = bucket_name or self.default_bucket
        try:
            return await asyncio.to_thread(
                self._presign_client.presigned_put_object,
                bucket,
                object_name,
                expires=expires,
            )
        except S3Error as exc:
            raise RuntimeError(f"Failed to presign PUT {object_name}: {exc}") from exc

    async def stat_object(
        self,
        object_name: str,
        bucket_name: str | None = None,
    ) -> tuple[int, str] | None:
        """HEAD 对象，返回 ``(size, etag)``；不存在返回 None。

        etag 为 S3 返回的十六进制串（单段 PUT 时即内容 md5，可能带引号）。
        """
        bucket = bucket_name or self.default_bucket
        try:
            stat = await asyncio.to_thread(self.client.stat_object, bucket, object_name)
        except S3Error:
            return None
        etag = (stat.etag or "").strip('"').lower()
        if stat.size is None:
            return None
        return stat.size, etag

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

    async def remove_files(
        self,
        object_names: list[str],
        bucket_name: str | None = None,
    ) -> list[str]:
        """批量删除对象，返回删除失败的对象名列表。

        S3 语义下删除不存在的键视为成功（no-op），因此缺失对象不算失败。
        """
        if not object_names:
            return []
        bucket = bucket_name or self.default_bucket

        def _remove() -> list[str]:
            errors = list(
                self.client.remove_objects(
                    bucket, [DeleteObject(name) for name in object_names]
                )
            )
            for err in errors:
                logger.warning(
                    "minio_remove_failed",
                    object=err.name,
                    code=err.code,
                    message=err.message,
                )
            return [err.name for err in errors if err.name]

        try:
            return await asyncio.to_thread(_remove)
        except S3Error as exc:
            raise RuntimeError(f"Failed to remove {len(object_names)} objects: {exc}") from exc

    async def list_object_names(
        self,
        prefix: str,
        bucket_name: str | None = None,
    ) -> list[tuple[str, int]]:
        """列出前缀下全部对象名与大小（递归），供孤儿对象扫描使用。"""
        bucket = bucket_name or self.default_bucket

        def _list() -> list[tuple[str, int]]:
            return [
                (obj.object_name, obj.size or 0)
                for obj in self.client.list_objects(bucket, prefix=prefix, recursive=True)
            ]

        try:
            return await asyncio.to_thread(_list)
        except S3Error as exc:
            raise RuntimeError(f"Failed to list objects with prefix {prefix}: {exc}") from exc

    # ---- multipart 分片上传（minio-py 7.2.x 原语为私有方法，薄封装隔离版本风险）----
    async def create_multipart_upload(
        self,
        object_name: str,
        bucket_name: str | None = None,
    ) -> str:
        """初始化分片上传，返回 uploadId。"""
        bucket = bucket_name or self.default_bucket
        try:
            return await asyncio.to_thread(
                self.client._create_multipart_upload, bucket, object_name, {}
            )
        except S3Error as exc:
            raise RuntimeError(f"Failed to create multipart upload {object_name}: {exc}") from exc

    async def presigned_part_url(
        self,
        object_name: str,
        upload_id: str,
        part_number: int,
        expires: timedelta,
        bucket_name: str | None = None,
    ) -> str:
        """返回单个分片的预签名直传 URL（浏览器 PUT，签名含 partNumber/uploadId）。"""
        bucket = bucket_name or self.default_bucket
        try:
            return await asyncio.to_thread(
                self._presign_client.get_presigned_url,
                "PUT",
                bucket,
                object_name,
                expires,
                None,
                None,
                None,
                {"partNumber": str(part_number), "uploadId": upload_id},
            )
        except S3Error as exc:
            raise RuntimeError(
                f"Failed to presign part {part_number} of {object_name}: {exc}"
            ) from exc

    async def list_multipart_parts(
        self,
        object_name: str,
        upload_id: str,
        bucket_name: str | None = None,
    ) -> list[MultipartPart]:
        """列出已上传分片（服务端真相，分页拉全）；会话不存在抛 MultipartSessionNotFoundError。"""
        bucket = bucket_name or self.default_bucket

        def _list() -> list[MultipartPart]:
            parts: list[MultipartPart] = []
            marker: str | None = None
            while True:
                result = self.client._list_parts(
                    bucket,
                    object_name,
                    upload_id,
                    max_parts=1000,
                    part_number_marker=marker,
                )
                parts.extend(
                    MultipartPart(
                        part_number=p.part_number,
                        etag=(p.etag or "").strip('"').lower(),
                        size=p.size or 0,
                    )
                    for p in result.parts
                )
                if not result.is_truncated:
                    return parts
                marker = result.next_part_number_marker

        try:
            return await asyncio.to_thread(_list)
        except S3Error as exc:
            if exc.code == "NoSuchUpload":
                raise MultipartSessionNotFoundError(upload_id) from exc
            raise RuntimeError(f"Failed to list parts of {object_name}: {exc}") from exc

    async def complete_multipart_upload(
        self,
        object_name: str,
        upload_id: str,
        parts: list[MultipartPart],
        bucket_name: str | None = None,
    ) -> None:
        """合并分片成对象（parts 按 part_number 升序，S3 要求）。"""
        bucket = bucket_name or self.default_bucket
        from minio.datatypes import Part

        sdk_parts = [Part(part_number=p.part_number, etag=p.etag) for p in parts]
        try:
            await asyncio.to_thread(
                self.client._complete_multipart_upload,
                bucket,
                object_name,
                upload_id,
                sdk_parts,
            )
        except S3Error as exc:
            if exc.code == "NoSuchUpload":
                raise MultipartSessionNotFoundError(upload_id) from exc
            raise RuntimeError(f"Failed to complete multipart upload {object_name}: {exc}") from exc

    async def abort_multipart_upload(
        self,
        object_name: str,
        upload_id: str,
        bucket_name: str | None = None,
    ) -> None:
        """放弃分片上传并释放已传分片的存储；会话不存在视为已清理。"""
        bucket = bucket_name or self.default_bucket
        try:
            await asyncio.to_thread(
                self.client._abort_multipart_upload, bucket, object_name, upload_id
            )
        except S3Error as exc:
            if exc.code == "NoSuchUpload":
                return
            raise RuntimeError(f"Failed to abort multipart upload {object_name}: {exc}") from exc


_minio_service: MinIOService | None = None


def get_minio_service() -> MinIOService:
    """返回懒初始化的 MinIO 服务单例。"""
    global _minio_service
    if _minio_service is None:
        _minio_service = MinIOService()
    return _minio_service
