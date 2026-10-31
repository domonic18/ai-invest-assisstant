"""复盘采集器共用件：CollectResult 构造工厂 + 参数归一 + 软超时判定。"""

from datetime import date, datetime, timezone
from typing import Any

from collector.core.base import CollectResult, CollectStatus


def coerce_trade_date(value: Any) -> date | None:
    """显式日期参数经 Celery JSON 后会变成 ISO 字符串。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def is_soft_timeout(exc: BaseException) -> bool:
    """Celery 软超时须向上传播（延迟导入避开 worker 入口的导入环）。"""
    from celery.exceptions import SoftTimeLimitExceeded

    return isinstance(exc, SoftTimeLimitExceeded)


def build_result(
    source: str,
    data_type: str,
    started_at: datetime,
    status: CollectStatus,
    *,
    message: str | None = None,
    errors: list[str] | None = None,
    items_collected: int = 0,
    items_stored: int = 0,
    metadata: dict[str, Any] | None = None,
) -> CollectResult:
    """统一收尾时刻与可选字段默认值（collector_log 落库形状单一来源）。"""
    return CollectResult(
        source=source,
        data_type=data_type,
        status=status,
        items_collected=items_collected,
        items_stored=items_stored,
        errors=errors or [],
        message=message,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        metadata=metadata or {},
    )
