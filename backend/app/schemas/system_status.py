"""后台服务连接状态 schema。"""

from datetime import datetime
from typing import Literal

from app.schemas.base import CamelModel


class ServiceStatusItem(CamelModel):
    """单个依赖服务的连通性探测结果。"""

    key: str
    name: str
    status: Literal["up", "down"]
    latency_ms: int | None = None
    detail: str | None = None
    error: str | None = None


class SystemStatusResponse(CamelModel):
    """全部依赖服务的连通性汇总。"""

    overall: Literal["operational", "degraded"]
    items: list[ServiceStatusItem]
    checked_at: datetime
