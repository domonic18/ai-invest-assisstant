"""采集健康监测服务：定时检测编排与快照读取组装。

``run_check`` 是检测入口（collector_health_check 定时任务与
管理端「立即检测」共用）：取数快照 → 纯函数判定 → diff 维护
``state_changed_at`` → upsert ``collector_health_status`` → 清理孤儿行。
读函数（overview/tasks/channels/schedule-check）只读快照表组装响应，
不在请求路径实时判定（schedule-check 除外，本质是运行记录核对查询）。
"""

from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ
from app.core.config import get_settings
from app.core.constants import TASK_TYPE_DOMAIN
from app.models.collector_health_status import CollectorHealthStatus
from app.models.collector_task import CollectorTask
from app.repositories.admin.collector_health_repository import (
    delete_orphan_snapshots,
    delete_snapshots,
    fetch_day_runs,
    fetch_instance_universe,
    fetch_latest_errors,
    load_health_rows,
    upsert_health_rows,
)
from app.repositories.market.kline_repository import fetch_trade_dates_between
from app.services.collector.cron_utils import cron_interval
from app.services.collector.health.health_judge import (
    InstanceVerdict,
    JudgeThresholds,
    apply_group_rules,
    build_schedule_rows,
    judge_instance,
)
from app.services.collector.health.health_snapshot import (
    InstanceFacts,
    build_instance_facts,
    build_snapshot,
)

HEALTH_CHECK_TASK_TYPE = "health-check"

logger = structlog.get_logger(__name__)


def _thresholds() -> JudgeThresholds:
    """从配置装配判定阈值。"""
    settings = get_settings()
    return JudgeThresholds(
        consecutive_windows_critical=settings.health_consecutive_windows_critical,
        consecutive_failures_degraded=settings.health_consecutive_failures_degraded,
        success_rate_7d_threshold=settings.health_success_rate_7d_threshold,
        high_freq_daily_rate_threshold=settings.health_high_freq_daily_rate_threshold,
        silent_days=settings.health_silent_days,
        schedule_grace_factor=settings.health_schedule_grace_factor,
        skipped_stall_windows=settings.health_skipped_stall_windows,
    )


def build_status_values(
    verdicts: list[InstanceVerdict],
    existing: dict[tuple[str, str], CollectorHealthStatus],
    checked_at: datetime,
) -> list[dict[str, object]]:
    """判定结果 → 快照行 dict（纯函数）：状态不变不动 state_changed_at。"""
    values: list[dict[str, object]] = []
    for verdict in verdicts:
        prev = existing.get((verdict.task_type, verdict.source))
        state_changed_at = (
            prev.state_changed_at
            if prev is not None and prev.status == verdict.status
            else checked_at
        )
        values.append(
            {
                "task_type": verdict.task_type,
                "source": verdict.source,
                "status": verdict.status,
                "role": verdict.role,
                "domain": verdict.domain,
                "success_rate_24h": verdict.success_rate_24h,
                "success_rate_7d": verdict.success_rate_7d,
                "consecutive_failures": verdict.consecutive_failures,
                "last_success_at": verdict.last_success_at,
                "windows_without_success": verdict.windows_without_success,
                "last_error_summary": verdict.last_error_summary,
                "last_error_cause": verdict.last_error_cause,
                "reasons": list(verdict.reasons),
                "is_high_frequency": verdict.is_high_frequency,
                "last_records_count": verdict.last_records_count,
                "last_records_date": verdict.last_records_date,
                "state_changed_at": state_changed_at,
                "checked_at": checked_at,
            }
        )
    return values


async def run_check(session: AsyncSession) -> dict[str, Any]:
    """执行一次全量健康检测并落库（调用方事务由本函数提交）。"""
    checked_at = datetime.now(timezone.utc)
    snapshot = await build_snapshot(session, checked_at)
    th = _thresholds()

    verdicts: list[InstanceVerdict] = []
    judge_failures = 0
    for facts in snapshot.instances:
        try:
            verdicts.append(judge_instance(facts, snapshot, th))
        except Exception:  # noqa: BLE001 — 单实例判定失败隔离，不阻断整批
            judge_failures += 1
            logger.exception(
                "health_judge_failed",
                task_type=facts.task_type,
                source=facts.source,
            )
    verdicts = apply_group_rules(verdicts, snapshot, th)

    existing_rows = await load_health_rows(session)
    existing = {(row.task_type, row.source): row for row in existing_rows}
    await upsert_health_rows(
        session, build_status_values(verdicts, existing, checked_at)
    )
    orphaned = await delete_orphan_snapshots(
        session, {(v.task_type, v.source) for v in verdicts}
    )
    await session.commit()

    status_counts = Counter(v.status for v in verdicts)
    return {
        "checked_at": checked_at,
        "total": len(verdicts),
        "failed": judge_failures,
        "orphaned": orphaned,
        "status_counts": dict(status_counts),
    }


# ---------------------------------------------------------------------------
# 读快照组装（页面只读，毫秒级小表查询）
# ---------------------------------------------------------------------------


async def _load_checked_at(session: AsyncSession) -> datetime | None:
    """快照批次检测时间（全表同值，取任意一行）。"""
    row = await session.scalar(
        select(CollectorHealthStatus.checked_at).limit(1)
    )
    return row if isinstance(row, datetime) else None


async def _load_stale_after(session: AsyncSession, checked_at: datetime) -> datetime:
    """检测延迟阈值 = checked_at + 检测间隔 × 倍数（间隔取自检测任务 cron）。"""
    settings = get_settings()
    schedule = await session.scalar(
        select(CollectorTask.schedule)
        .where(CollectorTask.task_type == HEALTH_CHECK_TASK_TYPE)
        .limit(1)
    )
    interval = cron_interval(schedule, datetime.now(timezone.utc))
    return checked_at + interval * settings.health_stale_after_multiplier


async def get_overview(session: AsyncSession) -> dict[str, Any]:
    """总览：健康分、状态计数、24h 成功率、分域概览、检测时间。"""
    rows = await load_health_rows(session)
    checked_at = await _load_checked_at(session)
    counts = Counter(row.status for row in rows)
    judgeable = sum(
        count
        for status, count in counts.items()
        if status not in ("paused", "unconfigured")
    )
    health_score = (
        round(
            100
            * (counts.get("healthy", 0) + 0.5 * counts.get("degraded", 0))
            / judgeable
        )
        if judgeable
        else 100
    )
    rates = [float(row.success_rate_24h) for row in rows if row.success_rate_24h is not None]
    domains: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = domains.setdefault(
            row.domain, {"total": 0, "healthy": 0, "degraded": 0,
                         "critical": 0, "silent": 0}
        )
        bucket["total"] += 1
        if row.status in bucket:
            bucket[row.status] += 1
    return {
        "health_score": health_score,
        "total": len(rows),
        "counts": {
            "healthy": counts.get("healthy", 0),
            "degraded": counts.get("degraded", 0),
            "critical": counts.get("critical", 0),
            "silent": counts.get("silent", 0),
            "paused": counts.get("paused", 0),
            "unconfigured": counts.get("unconfigured", 0),
        },
        "success_rate_24h": sum(rates) / len(rates) if rates else None,
        "domains": [
            {"domain": domain, **bucket} for domain, bucket in sorted(domains.items())
        ],
        "checked_at": checked_at,
        "stale_after": (
            await _load_stale_after(session, checked_at) if checked_at else None
        ),
    }


async def get_tasks(
    session: AsyncSession, *, domain: str | None = None, status: str | None = None
) -> list[dict[str, object]]:
    """实例明细：快照行 + join collector_task 取 cron/启用状态。"""
    rows = await load_health_rows(session)
    task_meta = {
        (task_type, source): (schedule, is_active)
        for task_type, source, schedule, is_active in (
            await session.execute(
                select(
                    CollectorTask.task_type,
                    CollectorTask.source,
                    CollectorTask.schedule,
                    CollectorTask.is_active,
                )
            )
        )
    }
    result: list[dict[str, object]] = []
    for row in rows:
        if domain and row.domain != domain:
            continue
        if status and row.status != status:
            continue
        schedule, is_active = task_meta.get(
            (row.task_type, row.source), (None, None)
        )
        result.append(
            {
                "task_type": row.task_type,
                "source": row.source,
                "status": row.status,
                "role": row.role,
                "domain": row.domain,
                "success_rate_24h": row.success_rate_24h,
                "success_rate_7d": row.success_rate_7d,
                "consecutive_failures": row.consecutive_failures,
                "windows_without_success": row.windows_without_success,
                "last_success_at": row.last_success_at,
                "last_error_summary": row.last_error_summary,
                "last_error_cause": row.last_error_cause,
                "reasons": list(row.reasons or []),
                "is_high_frequency": row.is_high_frequency,
                "last_records_count": row.last_records_count,
                "last_records_date": row.last_records_date,
                "state_changed_at": row.state_changed_at,
                "checked_at": row.checked_at,
                "schedule": schedule,
                "is_active": is_active,
            }
        )
    return result


async def get_channels(session: AsyncSession) -> list[dict[str, object]]:
    """渠道视图：按 source 聚合实例数/成功率/故障数/归因分布。"""
    rows = await load_health_rows(session)
    grouped: dict[str, list[CollectorHealthStatus]] = {}
    for row in rows:
        grouped.setdefault(row.source, []).append(row)

    result: list[dict[str, object]] = []
    for source, items in sorted(grouped.items()):
        rates = [float(r.success_rate_7d) for r in items if r.success_rate_7d is not None]
        causes = Counter(
            r.last_error_cause for r in items if r.last_error_cause
        )
        result.append(
            {
                "source": source,
                "domain_count": len({r.domain for r in items}),
                "instance_count": len(items),
                "success_rate_7d": sum(rates) / len(rates) if rates else None,
                "fault_count": sum(
                    1 for r in items if r.status in ("critical", "silent", "degraded")
                ),
                "causes": dict(causes),
            }
        )
    return result


def _cn_day_bounds(day: date) -> tuple[datetime, datetime]:
    """CN 日历日的 [前夜 -12h, 次日 +12h] aware UTC 窗口（跨日宽限兜底）。"""
    start = datetime.combine(day, time.min, tzinfo=CN_TZ)
    end = start + timedelta(days=1)
    return start - timedelta(hours=12), end + timedelta(hours=12)


async def get_schedule_check(session: AsyncSession, day: date) -> dict[str, Any]:
    """计划核对：任意历史日期的「应跑 vs 实跑」（按日志现算）。"""
    th = _thresholds()
    universe = [
        row
        for row in await fetch_instance_universe(session)
        if row.task_type in TASK_TYPE_DOMAIN
    ]
    since, until = _cn_day_bounds(day)
    errors = await fetch_latest_errors(session, until - timedelta(days=30))
    facts: list[InstanceFacts] = build_instance_facts(universe, [], {}, errors)
    day_runs = await fetch_day_runs(session, since, until)
    # 交易日历窗口锚定查询日（非今天）：查更早的历史日期时 is_trade_day 才不会误判为 false。
    trade_dates = await fetch_trade_dates_between(
        session, day - timedelta(days=45), day + timedelta(days=1)
    )
    rows = build_schedule_rows(
        facts, day_runs, trade_dates, day, th,
        now_cn=datetime.now(CN_TZ).replace(tzinfo=None),
    )
    return {
        "date": day,
        "is_trade_day": day in trade_dates,
        "items": [asdict(row) for row in rows],
    }


async def clear_snapshots(
    session: AsyncSession,
    *,
    task_type: str | None = None,
    source: str | None = None,
) -> int:
    """清空快照（可选过滤）；下个检测点或「立即检测」会重建。"""
    deleted = await delete_snapshots(session, task_type=task_type, source=source)
    await session.commit()
    return deleted
