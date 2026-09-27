"""MinIO 分片上传操作与 S3Error 翻译 helper。

基础对象操作在 ``minio_service``；本模块承载 multipart 会话生命周期
（minio-py 7.2.x 原语为私有方法，薄封装隔离版本风险）与全部方法共用的
``_to_thread_ok``（to_thread + S3Error→RuntimeError 统一翻译）。
异常与分片类型在此定义，经 ``minio_service`` 再导出兼容既有消费方。
"""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any, NamedTuple, TypeVar

from minio import Minio
from minio.error import S3Error

T = TypeVar("T")


class MultipartPart(NamedTuple):
    """已上传分片信息（etag 已去引号小写）。"""

    part_number: int
    etag: str
    size: int


class MultipartSessionNotFoundError(RuntimeError):
    """uploadId 不存在（已 complete/abort 或过期）。"""


async def _to_thread_ok(
    fn: Callable[..., T], *args: Any, what: str, **kwargs: Any
) -> T:
    """线程池执行 SDK 调用，S3Error 统一译为带上下文的 RuntimeError。"""
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except S3Error as exc:
        raise RuntimeError(f"{what}: {exc}") from exc


class MultipartUploadMixin:
    """multipart 分片上传（依赖宿主的 client/_presign_client/default_bucket）。"""

    client: Minio
    _presign_client: Minio
    default_bucket: str

    async def create_multipart_upload(
        self,
        object_name: str,
        bucket_name: str | None = None,
    ) -> str:
        """初始化分片上传，返回 uploadId。"""
        bucket = bucket_name or self.default_bucket
        return await _to_thread_ok(
            self.client._create_multipart_upload,
            bucket,
            object_name,
            {},
            what=f"Failed to create multipart upload {object_name}",
        )

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
        return await _to_thread_ok(
            self._presign_client.get_presigned_url,
            "PUT",
            bucket,
            object_name,
            expires,
            None,
            None,
            None,
            {"partNumber": str(part_number), "uploadId": upload_id},
            what=f"Failed to presign part {part_number} of {object_name}",
        )

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
