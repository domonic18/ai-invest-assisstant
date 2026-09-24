"""采集健康监测 API schema（camelCase wire 契约）。"""

from datetime import date, datetime

from pydantic import Field

from app.schemas.base import CamelModel


class HealthStatusCounts(CamelModel):
    """各状态实例计数。"""

    healthy: int
    degraded: int
    critical: int
    silent: int
    paused: int
    unconfigured: int


class HealthDomainSummary(CamelModel):
    """分域概览小计。"""

    domain: str
    total: int
    healthy: int
    degraded: int
    critical: int
    silent: int


class HealthOverviewResponse(CamelModel):
    """总览：健康分、状态计数、24h 成功率、检测时间与延迟阈值。"""

    health_score: int
    total: int
    counts: HealthStatusCounts
    success_rate_24h: float | None = Field(alias="successRate24h")
    domains: list[HealthDomainSummary]
    checked_at: datetime | None
    stale_after: datetime | None


class HealthTaskItem(CamelModel):
    """实例明细行（快照 + 任务配置）。"""

    task_type: str
    source: str
    status: str
    role: str
    domain: str
    success_rate_24h: float | None = Field(alias="successRate24h")
    success_rate_7d: float | None = Field(alias="successRate7d")
    consecutive_failures: int
    windows_without_success: int
    last_success_at: datetime | None
    last_error_summary: str | None
    last_error_cause: str | None
    reasons: list[str] = []
    is_high_frequency: bool
    last_records_count: int | None
    last_records_date: date | None
    state_changed_at: datetime
    checked_at: datetime
    schedule: str | None
    is_active: bool | None


class ChannelHealthItem(CamelModel):
    """渠道视图聚合行。"""

    source: str
    domain_count: int
    instance_count: int
    success_rate_7d: float | None = Field(alias="successRate7d")
    fault_count: int
    causes: dict[str, int]


class ScheduleCheckItem(CamelModel):
    """单实例某日计划核对行。"""

    task_type: str
    source: str
    domain: str
    role: str
    is_active: bool
    has_task_row: bool
    schedule: str | None
    window_total: int
    success_windows: int
    skipped_windows: int
    failed_windows: int
    missing_windows: int
    exempted: bool
    last_error_summary: str | None
    last_error_cause: str | None


class ScheduleCheckResponse(CamelModel):
    """计划核对响应：任意历史日期「应跑 vs 实跑」。"""

    date: date
    is_trade_day: bool
    items: list[ScheduleCheckItem]


class RunHealthCheckResponse(CamelModel):
    """立即检测结果摘要。"""

    checked_at: datetime
    total: int
    failed: int
    orphaned: int
    status_counts: dict[str, int]


class ClearSnapshotsResponse(CamelModel):
    """清空快照结果。"""

    deleted: int
