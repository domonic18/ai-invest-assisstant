"""健康快照组装：把判定所需的运行事实一次取齐为纯数据结构。

``build_snapshot`` 是包内唯一的 IO 组装点（全部走仓储查询），
产出的 :class:`HealthSnapshot` 交给 ``health_judge`` 纯函数判定，
保证判定逻辑零 IO、可单测。
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, now_cn
from app.core.constants import TASK_TYPE_DOMAIN
from app.repositories.admin.collector_health_repository import (
    ErrorRow,
    InstanceConfigRow,
    RunRow,
    SuccessRow,
    fetch_instance_universe,
    fetch_last_success_rows,
    fetch_latest_errors,
    fetch_recent_runs,
)
from app.repositories.market.kline_repository import fetch_trade_dates_between

# 取数窗口：运行明细 7 天（24h/7d 成功率），成功/错误回溯 30 天，
# 交易日历 35 天（覆盖静默判定的交易日计数）
RUNS_WINDOW_DAYS = 7
HISTORY_WINDOW_DAYS = 30
TRADE_CALENDAR_WINDOW_DAYS = 35


@dataclass(frozen=True)
class InstanceFacts:
    """单实例 (task_type, source) 的判定输入事实。"""

    task_type: str
    source: str
    domain: str
    role: str
    schedule: str | None
    is_active: bool
    has_task_row: bool
    runs: list[RunRow] = field(default_factory=list)
    last_success_at: datetime | None = None
    last_records_count: int | None = None
    last_records_date: date | None = None
    last_error_summary: str | None = None
    last_error_at: datetime | None = None


@dataclass(frozen=True)
class HealthSnapshot:
    """一次检测的完整判定输入（纯数据，零 IO）。"""

    checked_at: datetime
    now_cn_naive: datetime
    trade_dates: set[date]
    instances: list[InstanceFacts]


def _assign_roles(
    universe: list[InstanceConfigRow],
) -> dict[tuple[str, str], str]:
    """按渠道优先级分配主备角色：同 task_type 下 priority 最小为主渠道。

    无渠道关联（仅任务行，如 internal）或多渠道缺一的实例为 single。
    """
    by_type: dict[str, list[InstanceConfigRow]] = {}
    for row in universe:
        by_type.setdefault(row.task_type, []).append(row)

    roles: dict[tuple[str, str], str] = {}
    for task_type, rows in by_type.items():
        linked = sorted(
            (r for r in rows if r.priority is not None),
            key=lambda r: (r.priority, r.source),
        )
        linked_keys = {(r.task_type, r.source) for r in linked}
        if len(linked) <= 1:
            for row in rows:
                roles[(row.task_type, row.source)] = "single"
            continue
        for index, row in enumerate(linked):
            roles[(row.task_type, row.source)] = "primary" if index == 0 else "backup"
        for row in rows:
            if (row.task_type, row.source) not in linked_keys:
                roles[(row.task_type, row.source)] = "single"
    return roles


def build_instance_facts(
    universe: list[InstanceConfigRow],
    runs: list[RunRow],
    successes: dict[tuple[str, str], SuccessRow],
    errors: dict[tuple[str, str], ErrorRow],
) -> list[InstanceFacts]:
    """把查询结果按实例键归组为判定事实（纯函数，可单测）。"""
    roles = _assign_roles(universe)
    runs_by_key: dict[tuple[str, str], list[RunRow]] = {}
    for row in runs:
        runs_by_key.setdefault((row.task_type, row.source), []).append(row)

    facts: list[InstanceFacts] = []
    for config in universe:
        key = (config.task_type, config.source)
        success = successes.get(key)
        error = errors.get(key)
        facts.append(
            InstanceFacts(
                task_type=config.task_type,
                source=config.source,
                domain=TASK_TYPE_DOMAIN.get(config.task_type, "other"),
                role=roles.get(key, "single"),
                schedule=config.schedule,
                is_active=config.is_active,
                has_task_row=config.has_task_row,
                runs=runs_by_key.get(key, []),
                last_success_at=success.started_at if success else None,
                last_records_count=success.records_count if success else None,
                last_records_date=success.started_at.astimezone(CN_TZ).date()
                if success
                else None,
                last_error_summary=error.error_summary if error else None,
                last_error_at=error.started_at if error else None,
            )
        )
    return facts


async def build_snapshot(session: AsyncSession, checked_at: datetime) -> HealthSnapshot:
    """取数组装健康快照（唯一 IO 组装点）。"""
    history_since = checked_at - timedelta(days=HISTORY_WINDOW_DAYS)
    runs_since = checked_at - timedelta(days=RUNS_WINDOW_DAYS)
    today = now_cn().date()
    calendar_start = today - timedelta(days=TRADE_CALENDAR_WINDOW_DAYS)

    universe = [
        row
        for row in await fetch_instance_universe(session)
        if row.task_type in TASK_TYPE_DOMAIN
    ]
    trade_dates = await fetch_trade_dates_between(session, calendar_start, today)
    # runs 不按交易日过滤：周末重试/人工补跑也是真实记录（剔除会漏计
    # skipped 停滞串，且周末人工成功无法满足周五窗口宽限）；
    # 交易日豁免由窗口与静默判定通过 trade_dates 口径实现
    runs = await fetch_recent_runs(session, runs_since)
    successes = await fetch_last_success_rows(session, history_since)
    errors = await fetch_latest_errors(session, history_since)

    return HealthSnapshot(
        checked_at=checked_at,
        now_cn_naive=checked_at.astimezone(CN_TZ).replace(tzinfo=None),
        trade_dates=trade_dates,
        instances=build_instance_facts(universe, runs, successes, errors),
    )
