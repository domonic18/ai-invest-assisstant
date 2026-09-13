"""采集健康监测仓储：实例清单、日志聚合与健康快照读写。

取数口径（供 services.collector.health 判定引擎消费）：

- 实例清单 = ``collector_task`` 行 ∪ (``collector_channel_data_type`` ×
  ``collector_channel_config``) 关联对，键均为 ``(task_type, source)``；
- ``collector_log.task_name`` 存 TASK_SPECS 键（task_type），渠道身份
  一律按二元组联接，禁止用实例名 ``collector_task.task_name`` 查日志；
- 运行明细只取终态窄列（status/started_at），错误原文用 DISTINCT ON
  每实例仅取最近一条，避免整表 error_msg 搬运。
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_channel_config import CollectorChannelConfig
from app.models.collector_channel_data_type import CollectorChannelDataType
from app.models.collector_health_status import CollectorHealthStatus
from app.models.collector_log import CollectorLog
from app.models.collector_task import CollectorTask

# 终态集合：running/pending 是进行态，不参与健康判定
TERMINAL_STATUSES = ("success", "partial", "failed", "skipped")

# 每实例保留的错误摘要长度（快照列 VARCHAR(500)）
ERROR_SUMMARY_MAX = 500


@dataclass(frozen=True)
class InstanceConfigRow:
    """实例清单行：(task_type, source) 粒度的任务/渠道配置。"""

    task_type: str
    source: str
    schedule: str | None
    is_active: bool
    has_task_row: bool
    priority: int | None


@dataclass(frozen=True)
class RunRow:
    """终态运行窄行（不含 error_msg）。"""

    task_type: str
    source: str
    status: str
    started_at: datetime


@dataclass(frozen=True)
class SuccessRow:
    """最近一次成功运行（DISTINCT ON）。"""

    task_type: str
    source: str
    started_at: datetime
    records_count: int


@dataclass(frozen=True)
class ErrorRow:
    """最近一次失败运行的错误摘要（DISTINCT ON）。"""

    task_type: str
    source: str
    started_at: datetime
    error_summary: str


async def fetch_instance_universe(session: AsyncSession) -> list[InstanceConfigRow]:
    """实例全集：collector_task 行 ∪ 渠道关联对（键去重，任务行优先）。"""
    task_rows = (
        (await session.execute(
            select(
                CollectorTask.task_type,
                CollectorTask.source,
                CollectorTask.schedule,
                CollectorTask.is_active,
            )
        ))
        .all()
    )
    channel_rows = (
        (await session.execute(
            select(
                CollectorChannelDataType.data_type,
                CollectorChannelConfig.source,
                CollectorChannelDataType.priority,
            )
            .join(
                CollectorChannelConfig,
                CollectorChannelConfig.id == CollectorChannelDataType.channel_id,
            )
            .where(CollectorChannelConfig.is_enabled.is_(True))
        ))
        .all()
    )

    merged: dict[tuple[str, str], InstanceConfigRow] = {}
    for task_type, source, schedule, is_active in task_rows:
        merged[(task_type, source)] = InstanceConfigRow(
            task_type=task_type,
            source=source,
            schedule=schedule,
            is_active=bool(is_active),
            has_task_row=True,
            priority=None,
        )
    for data_type, source, priority in channel_rows:
        key = (data_type, source)
        existing = merged.get(key)
        if existing is not None:
            merged[key] = InstanceConfigRow(
                task_type=existing.task_type,
                source=existing.source,
                schedule=existing.schedule,
                is_active=existing.is_active,
                has_task_row=True,
                priority=priority,
            )
        else:
            merged[key] = InstanceConfigRow(
                task_type=data_type,
                source=source,
                schedule=None,
                is_active=True,
                has_task_row=False,
                priority=priority,
            )
    return list(merged.values())


async def fetch_recent_runs(
    session: AsyncSession, since: datetime
) -> list[RunRow]:
    """since 起的全部终态运行窄行（升序），源 unknown 的脏行排除。"""
    rows = (
        (await session.execute(
            select(
                CollectorLog.task_name,
                CollectorLog.source,
                CollectorLog.status,
                CollectorLog.started_at,
            )
            .where(
                CollectorLog.started_at >= since,
                CollectorLog.status.in_(TERMINAL_STATUSES),
                CollectorLog.source.isnot(None),
                CollectorLog.source != "unknown",
            )
            .order_by(CollectorLog.started_at.asc())
        ))
        .all()
    )
    return [
        RunRow(task_type=t, source=s, status=st, started_at=at)
        for t, s, st, at in rows
    ]


async def fetch_day_runs(session: AsyncSession, since: datetime, until: datetime) -> list[RunRow]:
    """计划核对用：[since, until) 窗口内终态运行窄行（升序）。"""
    rows = (
        (await session.execute(
            select(
                CollectorLog.task_name,
                CollectorLog.source,
                CollectorLog.status,
                CollectorLog.started_at,
            )
            .where(
                CollectorLog.started_at >= since,
                CollectorLog.started_at < until,
                CollectorLog.status.in_(TERMINAL_STATUSES),
                CollectorLog.source.isnot(None),
                CollectorLog.source != "unknown",
            )
            .order_by(CollectorLog.started_at.asc())
        ))
        .all()
    )
    return [
        RunRow(task_type=t, source=s, status=st, started_at=at)
        for t, s, st, at in rows
    ]


async def fetch_last_success_rows(
    session: AsyncSession, since: datetime
) -> dict[tuple[str, str], SuccessRow]:
    """每实例最近一次成功运行（30d 窗口 DISTINCT ON）。"""
    rows = (
        (await session.execute(
            select(
                CollectorLog.task_name,
                CollectorLog.source,
                CollectorLog.started_at,
                CollectorLog.records_count,
            )
            .where(
                CollectorLog.started_at >= since,
                CollectorLog.status == "success",
                CollectorLog.source.isnot(None),
                CollectorLog.source != "unknown",
            )
            .distinct(CollectorLog.task_name, CollectorLog.source)
            .order_by(
                CollectorLog.task_name,
                CollectorLog.source,
                CollectorLog.started_at.desc(),
            )
        ))
        .all()
    )
    return {
        (task_type, source): SuccessRow(task_type, source, started_at, records_count)
        for task_type, source, started_at, records_count in rows
    }


async def fetch_latest_errors(
    session: AsyncSession, since: datetime
) -> dict[tuple[str, str], ErrorRow]:
    """每实例最近一次失败运行的错误摘要（30d 窗口 DISTINCT ON）。"""
    rows = (
        (await session.execute(
            select(
                CollectorLog.task_name,
                CollectorLog.source,
                CollectorLog.started_at,
                CollectorLog.error_msg,
            )
            .where(
                CollectorLog.started_at >= since,
                CollectorLog.status == "failed",
                CollectorLog.error_msg.isnot(None),
                CollectorLog.error_msg != "",
                CollectorLog.source.isnot(None),
                CollectorLog.source != "unknown",
            )
            .distinct(CollectorLog.task_name, CollectorLog.source)
            .order_by(
                CollectorLog.task_name,
                CollectorLog.source,
                CollectorLog.started_at.desc(),
            )
        ))
        .all()
    )
    return {
        (task_type, source): ErrorRow(
            task_type, source, started_at, (error_msg or "")[:ERROR_SUMMARY_MAX]
        )
        for task_type, source, started_at, error_msg in rows
    }


async def load_health_rows(session: AsyncSession) -> list[CollectorHealthStatus]:
    """读全量健康快照行（常驻约 50 行 + 可能的历史残留）。"""
    return list(
        (await session.execute(select(CollectorHealthStatus))).scalars().all()
    )


async def upsert_health_rows(
    session: AsyncSession, values: list[dict[str, object]]
) -> None:
    """按 (task_type, source) 批量 upsert 快照行（不提交，事务归服务层）。"""
    if not values:
        return
    column_names = [
        "task_type", "source", "status", "role", "domain",
        "success_rate_24h", "success_rate_7d", "consecutive_failures",
        "last_success_at", "windows_without_success",
        "last_error_summary", "last_error_cause", "reasons", "is_high_frequency",
        "last_records_count", "last_records_date",
        "state_changed_at", "checked_at",
    ]
    payload = [{name: row[name] for name in column_names} for row in values]
    stmt = pg_insert(CollectorHealthStatus).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["task_type", "source"],
        set_={name: stmt.excluded[name] for name in column_names
              if name not in ("task_type", "source")},
    )
    await session.execute(stmt)


async def delete_orphan_snapshots(
    session: AsyncSession, valid_keys: set[tuple[str, str]]
) -> int:
    """删除实例清单中已不存在的快照行，返回删除行数（不提交）。"""
    existing = await load_health_rows(session)
    orphan_ids = [
        row.id
        for row in existing
        if (row.task_type, row.source) not in valid_keys
    ]
    if not orphan_ids:
        return 0
    await session.execute(
        delete(CollectorHealthStatus).where(CollectorHealthStatus.id.in_(orphan_ids))
    )
    return len(orphan_ids)


async def delete_snapshots(
    session: AsyncSession,
    *,
    task_type: str | None = None,
    source: str | None = None,
) -> int:
    """按可选过滤条件删除快照行，返回删除行数（不提交）。"""
    stmt = delete(CollectorHealthStatus)
    if task_type:
        stmt = stmt.where(CollectorHealthStatus.task_type == task_type)
    if source:
        stmt = stmt.where(CollectorHealthStatus.source == source)
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)
