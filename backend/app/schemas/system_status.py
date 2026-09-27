"""后台服务连接状态 schema。"""

from datetime import datetime
from typing import Literal

from app.schemas.base import CamelModel


class ServiceStatusItem(CamelModel):
    """单个依赖服务的连通性探测结果。"""

    key: str
    name: str
    category: Literal["storage", "compute", "external"]
    status: Literal["up", "down"]
    latency_ms: int | None = None
    detail: str | None = None
    error: str | None = None


class SystemStatusResponse(CamelModel):
    """全部依赖服务的连通性汇总。"""

    overall: Literal["operational", "degraded"]
    items: list[ServiceStatusItem]
    checked_at: datetime


CeleryTaskState = Literal["pending", "running", "success", "partial", "failed", "skipped"]


class CeleryTaskSquare(CamelModel):
    """方框网格中的单个任务（一框一任务实例）。"""

    key: str
    task_type: str
    label: str
    state: CeleryTaskState
    source: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    detail: str | None = None


class CeleryQueueStatus(CamelModel):
    """单个 Celery 队列的任务方框集合。"""

    name: str
    label: str
    pending_total: int = 0
    tasks: list[CeleryTaskSquare] = []


class CeleryQueuesResponse(CamelModel):
    """三队列任务状态总览；broker 不可达时 broker_ok=false 降级仅展示 DB 侧。"""

    broker_ok: bool
    queues: list[CeleryQueueStatus]
    checked_at: datetime
