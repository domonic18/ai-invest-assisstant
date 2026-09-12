"""后台服务连接状态探测：并发检查 PostgreSQL / Redis / Elasticsearch / MinIO。

任一服务探测失败只降级该项（status=down + error），不影响其他项；
单服务探测超时由 ``settings.status_probe_timeout`` 控制，避免端点被
慢依赖拖挂。
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import sqlalchemy as sa
import structlog
from elasticsearch import AsyncElasticsearch
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import get_settings
from app.schemas.system_status import ServiceStatusItem, SystemStatusResponse
from app.services.common.minio_service import get_minio_service

logger = structlog.get_logger(__name__)


class SystemStatusService:
    """探测 web-api 运行依赖的存储/缓存/搜索/对象存储连通性。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_status(self) -> SystemStatusResponse:
        """并发探测全部依赖服务，返回各项状态与整体判定。"""
        items = await asyncio.gather(
            self._probe("postgres", "PostgreSQL", self._check_postgres),
            self._probe("redis", "Redis", self._check_redis),
            self._probe("elasticsearch", "Elasticsearch", self._check_elasticsearch),
            self._probe("minio", "MinIO", self._check_minio),
        )
        overall = "operational" if all(i.status == "up" for i in items) else "degraded"
        return SystemStatusResponse(
            overall=overall,  # type: ignore[arg-type]
            items=list(items),
            checked_at=datetime.now(timezone.utc),
        )

    async def _probe(
        self, key: str, name: str, check: Callable[[], Awaitable[str]]
    ) -> ServiceStatusItem:
        """包装单项探测：计时 + 超时 + 异常降级。"""
        timeout = get_settings().status_probe_timeout
        start = time.perf_counter()
        try:
            detail = await asyncio.wait_for(check(), timeout=timeout)
        except asyncio.TimeoutError:
            return ServiceStatusItem(
                key=key, name=name, status="down", error=f"探测超时（>{timeout}s）"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("status_probe_failed", service=key, error=str(exc))
            return ServiceStatusItem(
                key=key, name=name, status="down", error=str(exc) or type(exc).__name__
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ServiceStatusItem(
            key=key, name=name, status="up", latency_ms=latency_ms, detail=detail
        )

    async def _check_postgres(self) -> str:
        """复用请求会话执行 SELECT，验证数据库链路与版本。"""
        result = await self.session.execute(sa.text("SELECT version()"))
        version = str(result.scalar_one())
        # "PostgreSQL 16.4 (Ubuntu ...) on ..., compiled by ..." → "PostgreSQL 16.4"
        return " ".join(version.split()[:2])

    async def _check_redis(self) -> str:
        """PING 探测（复用容错客户端的连接超时配置）。"""
        return "PONG" if await get_redis().ping() else "no reply"

    async def _check_elasticsearch(self) -> str:
        """短生命周期客户端探测集群版本，用后即关。"""
        timeout = get_settings().status_probe_timeout
        client = AsyncElasticsearch(get_settings().elasticsearch_url)
        try:
            info = await client.options(request_timeout=timeout).info()
            return f"v{info['version']['number']}"
        finally:
            await client.close()

    async def _check_minio(self) -> str:
        """校验默认 bucket 可达（bucket 缺失在 detail 中标注，不判为连接故障）。"""
        service = get_minio_service()
        bucket = service.default_bucket
        exists = await asyncio.to_thread(service.client.bucket_exists, bucket)
        return f"bucket {bucket} {'可访问' if exists else '不存在（未初始化）'}"
