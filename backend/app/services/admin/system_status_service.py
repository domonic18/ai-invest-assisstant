"""后台服务连接状态探测：并发检查存储 / 调度计算 / 外部依赖三类服务。

任一服务探测失败只降级该项（status=down + error），不影响其他项；
单服务探测超时由 ``settings.status_probe_timeout`` 控制，避免端点被
慢依赖拖挂。``overall`` 只由 storage + compute 两类判定，external 类
（LLM 配置清单）仅作展示。

外部行情数据源（sina/东财/tushare 等）不做主动探测：东财 WAF 按主机
封禁，周期性探测反而自招封锁；数据新鲜度监控由采集健康页承担。
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Literal

import httpx
import redis.asyncio as aioredis
import sqlalchemy as sa
import structlog
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.douyin.signer_client import DouyinSignerClient
from app.core.cache import get_redis
from app.core.config import get_settings
from app.models.llm_config import LLMConfig
from app.schemas.system_status import ServiceStatusItem, SystemStatusResponse
from app.services.common.minio_service import get_minio_service

logger = structlog.get_logger(__name__)

#: celery inspect ping 的应答收集窗口（秒）。inspect 会等满窗口，须留出
#: status_probe_timeout（默认 3s）内的处理余量；真实假活是全程无应答，不受影响
INSPECT_PING_TIMEOUT = 1.5

#: 期望在线的 worker 节点名前缀（主 worker realtime@ 消费 realtime+batch，heavy@ 消费 heavy）
EXPECTED_WORKER_PREFIXES = ("realtime", "heavy")

#: LLM 配置用途及展示顺序
LLM_PURPOSES = ("chat", "vision", "embedding")

#: broker 短连接 socket 超时（秒）
BROKER_SOCKET_TIMEOUT = 2.0

ServiceCategory = Literal["storage", "compute", "external"]


class SystemStatusService:
    """探测 web-api 运行依赖的存储/调度计算/外部服务连通性。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _check_plan(
        self,
    ) -> list[tuple[str, str, ServiceCategory, Callable[[], Awaitable[str]]]]:
        """返回 (key, 展示名, 类别, 探测函数) 清单；未配置的可选服务直接省略。"""
        settings = get_settings()
        plan: list[tuple[str, str, ServiceCategory, Callable[[], Awaitable[str]]]] = [
            ("postgres", "PostgreSQL", "storage", self._check_postgres),
            ("redis", "Redis", "storage", self._check_redis),
            ("minio", "MinIO / COS", "storage", self._check_minio),
            ("celery-broker", "Celery Broker", "compute", self._check_celery_broker),
            ("celery-workers", "Celery Workers", "compute", self._check_celery_workers),
        ]
        if settings.paper_trade_url:
            plan.append(("paper-trade", "模拟盘柜台", "compute", self._check_paper_trade))
        if settings.douyin_signer_url:
            plan.append(("douyin-signer", "抖音签名服务", "compute", self._check_douyin_signer))
        plan.append(("llm-configs", "LLM 模型配置", "external", self._check_llm_configs))
        return plan

    async def get_status(self) -> SystemStatusResponse:
        """并发探测全部依赖服务，返回各项状态与整体判定。"""
        items = await asyncio.gather(
            *(self._probe(key, name, category, check) for key, name, category, check in self._check_plan())
        )
        core = [i for i in items if i.category in ("storage", "compute")]
        overall = "operational" if all(i.status == "up" for i in core) else "degraded"
        return SystemStatusResponse(
            overall=overall,  # type: ignore[arg-type]
            items=list(items),
            checked_at=datetime.now(timezone.utc),
        )

    async def _probe(
        self,
        key: str,
        name: str,
        category: ServiceCategory,
        check: Callable[[], Awaitable[str]],
    ) -> ServiceStatusItem:
        """包装单项探测：计时 + 超时 + 异常降级。"""
        timeout = get_settings().status_probe_timeout
        start = time.perf_counter()
        try:
            detail = await asyncio.wait_for(check(), timeout=timeout)
        except asyncio.TimeoutError:
            return ServiceStatusItem(
                key=key,
                name=name,
                category=category,
                status="down",
                error=f"探测超时（>{timeout}s）",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("status_probe_failed", service=key, error=str(exc))
            return ServiceStatusItem(
                key=key,
                name=name,
                category=category,
                status="down",
                error=str(exc) or type(exc).__name__,
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ServiceStatusItem(
            key=key,
            name=name,
            category=category,
            status="up",
            latency_ms=latency_ms,
            detail=detail,
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

    async def _check_minio(self) -> str:
        """校验默认 bucket 可达（bucket 缺失在 detail 中标注，不判为连接故障）。"""
        service = get_minio_service()
        bucket = service.default_bucket
        exists = await asyncio.to_thread(service.client.bucket_exists, bucket)
        return f"bucket {bucket} {'可访问' if exists else '不存在（未初始化）'}"

    async def _check_celery_broker(self) -> str:
        """PING Celery 专用 broker（与应用缓存 Redis 分列，独立短连接）。"""
        client = aioredis.from_url(
            str(get_settings().celery_broker_url),
            socket_connect_timeout=BROKER_SOCKET_TIMEOUT,
            socket_timeout=BROKER_SOCKET_TIMEOUT,
        )
        try:
            return "PONG" if await client.ping() else "no reply"
        except RedisError as exc:
            raise RuntimeError(f"broker 不可达: {exc}") from exc
        finally:
            await client.aclose()

    async def _check_celery_workers(self) -> str:
        """inspect ping 探活 worker 节点（假活检测：不消费的节点不应答）。"""
        from collector.celery_app import (
            app as celery_app,  # 函数内延迟导入（services↔collector 解环同规）
        )

        def _ping() -> dict[str, object]:
            return dict(celery_app.control.inspect(timeout=INSPECT_PING_TIMEOUT).ping() or {})

        replies = await asyncio.to_thread(_ping)
        online = sorted(replies.keys())
        if not online:
            raise RuntimeError("无节点应答（Broker 不可达或 worker 全部离线）")
        missing = [
            prefix
            for prefix in EXPECTED_WORKER_PREFIXES
            if not any(node.split("@", 1)[0] == prefix for node in online)
        ]
        if missing:
            raise RuntimeError(
                f"{'、'.join(missing)} 队列节点离线（应答：{', '.join(online)}）"
            )
        return f"{len(online)}/{len(EXPECTED_WORKER_PREFIXES)} 节点应答：{', '.join(online)}"

    async def _check_paper_trade(self) -> str:
        """探活模拟盘柜台适配器（/health 固定应答，不含掘金上游探活）。"""
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.status_probe_timeout) as client:
            response = await client.get(f"{settings.paper_trade_url.rstrip('/')}/health")
            response.raise_for_status()
            payload = response.json()
        if payload.get("status") != "ok":
            raise RuntimeError(f"异常应答：{payload}")
        return "适配器在线"

    async def _check_douyin_signer(self) -> str:
        """探测签名 sidecar /health（status=ok 且上报热身槽位）。"""
        payload = await DouyinSignerClient(get_settings().douyin_signer_url).health()
        if payload.get("status") != "ok":
            raise RuntimeError(str(payload.get("detail") or payload))
        warm = payload.get("warm_slots")
        return "在线" + (f"（热身槽位 {warm}）" if warm is not None else "")

    async def _check_llm_configs(self) -> str:
        """按用途统计已启用 LLM 配置（仅清单展示，不做真实 API 探测）。"""
        rows = (
            await self.session.execute(
                sa.select(LLMConfig.purpose, sa.func.count())
                .where(LLMConfig.is_active.is_(True))
                .group_by(LLMConfig.purpose)
            )
        ).all()
        counts = {purpose: int(n) for purpose, n in rows}
        total = sum(counts.values())
        if total == 0:
            raise RuntimeError("无已启用的 LLM 配置")
        breakdown = " · ".join(f"{p}×{counts[p]}" for p in LLM_PURPOSES if counts.get(p))
        return f"{total} 个启用配置（{breakdown}）· 仅展示配置就绪，未探测连通性"
