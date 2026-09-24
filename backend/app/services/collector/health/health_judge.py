"""健康判定引擎（纯函数，零 IO，可单测）。

判定输入是 :mod:`health_snapshot` 组装的 :class:`HealthSnapshot`，
输出是每实例的 :class:`InstanceVerdict` 与计划核对行。判定顺序短路：

paused → unconfigured → silent（交易日口径）→ critical（连缺应跑窗口）
→ degraded（7d 成功率/连败/连续 skipped 停滞/高频当日口径/主渠道故障备顶上）
→ healthy；skipped 全程良性。

另含跨实例组规则（全渠道断供升级 critical）与计划核对
（schedule-check，按任意历史日期核对「应跑 vs 实跑」）。
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta

from croniter import croniter

from app.core.clock import CN_TZ
from app.repositories.admin.collector_health_repository import RunRow
from app.services.collector.cron_utils import cron_cadence
from app.services.collector.health.error_classifier import classify_error
from app.services.collector.health.health_snapshot import (
    HealthSnapshot,
    InstanceFacts,
)

STATUS_HEALTHY = "healthy"
STATUS_DEGRADED = "degraded"
STATUS_CRITICAL = "critical"
STATUS_SILENT = "silent"
STATUS_PAUSED = "paused"
STATUS_UNCONFIGURED = "unconfigured"

# 高频任务：单日计划触发场次 >= 48
HIGH_FREQUENCY_DAILY_RUNS = 48
# 成功率规则的最小样本数（避免人工零星跑次造成误判）
MIN_RATE_DENOM_7D = 5
MIN_RATE_DENOM_DAILY = 8
# 计划窗口回看天数（交易日口径）
WINDOW_LOOKBACK_DAYS = 4


@dataclass(frozen=True)
class JudgeThresholds:
    """判定阈值（由 config.health_* 装配，保持判定器纯净）。"""

    consecutive_windows_critical: int = 2
    consecutive_failures_degraded: int = 3
    success_rate_7d_threshold: float = 0.90
    high_freq_daily_rate_threshold: float = 0.80
    silent_days: int = 7
    schedule_grace_factor: float = 1.5
    skipped_stall_windows: int = 3


@dataclass
class InstanceVerdict:
    """单实例判定结果（与快照表列一一对应 + reasons 调试信息）。"""

    task_type: str
    source: str
    status: str
    role: str
    domain: str
    success_rate_24h: float | None = None
    success_rate_7d: float | None = None
    consecutive_failures: int = 0
    windows_without_success: int = 0
    last_success_at: datetime | None = None
    last_error_summary: str | None = None
    last_error_cause: str | None = None
    is_high_frequency: bool = False
    last_records_count: int | None = None
    last_records_date: date | None = None
    reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# cron 窗口工具
# ---------------------------------------------------------------------------


def day_triggers(schedule: str, day: date) -> list[datetime]:
    """cron 在指定 CN 日历日的全部触发时刻（naive CN，按日截断）。"""
    base = datetime.combine(day, time.min)
    end = base + timedelta(days=1)
    try:
        it = croniter(schedule, base)
    except Exception:  # noqa: BLE001
        return []
    out: list[datetime] = []
    try:
        while len(out) < 2000:
            moment = it.get_next(datetime)
            if moment >= end:
                break
            out.append(moment)
    except Exception:  # noqa: BLE001
        return out
    return out


def _window_grace(facts: InstanceFacts, checked_at: datetime, th: JudgeThresholds) -> timedelta:
    """窗口宽限 = 名义节奏（相邻触发最小间隔）× 宽限系数。"""
    return cron_cadence(facts.schedule, checked_at) * th.schedule_grace_factor


def _naive_cn(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(CN_TZ).replace(tzinfo=None)


def _expected_windows(
    schedule: str | None,
    trade_dates: set[date],
    now_cn: datetime,
    grace: timedelta,
) -> list[datetime]:
    """回看期内「已过宽限期」的应跑窗口触发时刻（naive CN，升序）。

    未到触发时刻或仍在宽限内的窗口不计入，避免把未来窗口误判为缺失。
    """
    if not schedule:
        return []
    windows: list[datetime] = []
    for offset in range(WINDOW_LOOKBACK_DAYS - 1, -1, -1):
        day = (now_cn - timedelta(days=offset)).date()
        if day not in trade_dates:
            continue
        windows.extend(
            trigger
            for trigger in day_triggers(schedule, day)
            if trigger + grace <= now_cn
        )
    return windows


def _satisfied(
    times: list[datetime], trigger: datetime, grace: timedelta
) -> bool:
    """[trigger, trigger+grace) 内是否存在任一时刻（times 升序）。"""
    lo = bisect_left(times, trigger)
    hi = bisect_right(times, trigger + grace)
    return lo < hi


# ---------------------------------------------------------------------------
# 比率与连击
# ---------------------------------------------------------------------------


def _rate(runs: list[RunRow], since: datetime, until: datetime) -> float | None:
    """区间成功率：success / (success+partial+failed)，skipped 剔除。"""
    success = failed = 0
    for run in runs:
        if not (since <= run.started_at <= until):
            continue
        if run.status == "success":
            success += 1
        elif run.status in ("failed", "partial"):
            failed += 1
    denom = success + failed
    if denom == 0:
        return None
    return success / denom


def _leading_streak(runs_desc: list[RunRow], statuses: set[str]) -> int:
    """最近连续处于给定状态的次数（runs_desc 为时间降序）。"""
    count = 0
    for run in runs_desc:
        if run.status in statuses:
            count += 1
        else:
            break
    return count


# ---------------------------------------------------------------------------
# 单实例判定
# ---------------------------------------------------------------------------


def judge_instance(
    facts: InstanceFacts,
    snapshot: HealthSnapshot,
    th: JudgeThresholds,
) -> InstanceVerdict:
    """按序短路判定单实例健康状态。"""
    runs_desc = sorted(facts.runs, key=lambda r: r.started_at, reverse=True)
    now_cn = snapshot.now_cn_naive
    verdict = InstanceVerdict(
        task_type=facts.task_type,
        source=facts.source,
        status=STATUS_HEALTHY,
        role=facts.role,
        domain=facts.domain,
        success_rate_24h=_rate(facts.runs, snapshot.checked_at - timedelta(hours=24), snapshot.checked_at),
        success_rate_7d=_rate(facts.runs, snapshot.checked_at - timedelta(days=7), snapshot.checked_at),
        consecutive_failures=_leading_streak(runs_desc, {"failed"}),
        last_success_at=facts.last_success_at,
        last_error_summary=facts.last_error_summary,
        last_error_cause=classify_error(facts.last_error_summary),
        is_high_frequency=len(day_triggers(facts.schedule or "", now_cn.date()))
        >= HIGH_FREQUENCY_DAILY_RUNS,
        last_records_count=facts.last_records_count,
        last_records_date=facts.last_records_date,
    )

    # 1. 渠道关联但无任务行 → 未配置
    if not facts.has_task_row:
        verdict.status = STATUS_UNCONFIGURED
        verdict.reasons.append("无 collector_task 实例行")
        return verdict
    # 2. 任务停用
    if not facts.is_active:
        verdict.status = STATUS_PAUSED
        verdict.reasons.append("任务已停用")
        return verdict
    # 3. 静默：按交易日计数的成功间隔超阈值（节假日豁免）
    if _is_silent(facts, snapshot, th):
        verdict.status = STATUS_SILENT
        verdict.reasons.append(f"超过 {th.silent_days} 个交易日无成功")
        return verdict

    grace = _window_grace(facts, snapshot.checked_at, th)
    windows = _expected_windows(facts.schedule, snapshot.trade_dates, now_cn, grace)
    cover_times = sorted(
        _naive_cn(run.started_at)
        for run in facts.runs
        if run.status in ("success", "skipped")
    )
    missing = 0
    for trigger in reversed(windows):
        if _satisfied(cover_times, trigger, grace):
            break
        missing += 1
    verdict.windows_without_success = missing
    # 4. critical：连缺 ≥ 阈值个应成功窗口
    if missing >= th.consecutive_windows_critical:
        verdict.status = STATUS_CRITICAL
        verdict.reasons.append(f"连续 {missing} 个计划窗口未成功")
        return verdict

    # 5. degraded
    if (
        verdict.success_rate_7d is not None
        and sum(1 for r in facts.runs
                if snapshot.checked_at - timedelta(days=7) <= r.started_at
                and r.status != "skipped") >= MIN_RATE_DENOM_7D
        and verdict.success_rate_7d < th.success_rate_7d_threshold
    ):
        verdict.status = STATUS_DEGRADED
        verdict.reasons.append(f"7d 成功率 {verdict.success_rate_7d:.0%}")
    if verdict.consecutive_failures >= th.consecutive_failures_degraded:
        verdict.status = STATUS_DEGRADED
        verdict.reasons.append(f"连续失败 {verdict.consecutive_failures} 次")
    skipped_streak = _leading_streak(runs_desc, {"skipped"})
    if skipped_streak >= th.skipped_stall_windows:
        verdict.status = STATUS_DEGRADED
        verdict.reasons.append(f"连续 skipped {skipped_streak} 次产出停滞")
    if verdict.is_high_frequency:
        daily_rate = _high_freq_daily_rate(facts, snapshot)
        if daily_rate is not None and daily_rate < th.high_freq_daily_rate_threshold:
            verdict.status = STATUS_DEGRADED
            verdict.reasons.append(f"高频当日成功率 {daily_rate:.0%}")
    return verdict


def _is_silent(facts: InstanceFacts, snapshot: HealthSnapshot, th: JudgeThresholds) -> bool:
    """成功间隔（按交易日计数）是否超过静默阈值。"""
    today = snapshot.now_cn_naive.date()
    window_start = (snapshot.checked_at - timedelta(days=30)).astimezone(CN_TZ).date()
    if facts.last_success_at is None:
        gap_start = window_start
    else:
        gap_start = _naive_cn(facts.last_success_at).date()
        if gap_start <= window_start:
            gap_start = window_start
    return (
        sum(1 for d in snapshot.trade_dates if gap_start < d <= today)
        > th.silent_days
    )


def _high_freq_daily_rate(facts: InstanceFacts, snapshot: HealthSnapshot) -> float | None:
    """高频任务最近一个有运行的交易日的当日成功率。"""
    runs_by_day: dict[date, list[RunRow]] = {}
    for run in facts.runs:
        runs_by_day.setdefault(_naive_cn(run.started_at).date(), []).append(run)
    for offset in range(0, 8):
        day = snapshot.now_cn_naive.date() - timedelta(days=offset)
        day_runs = runs_by_day.get(day)
        if not day_runs:
            continue
        success = sum(1 for r in day_runs if r.status == "success")
        failed = sum(1 for r in day_runs if r.status in ("failed", "partial"))
        denom = success + failed
        if denom < MIN_RATE_DENOM_DAILY:
            return None
        return success / denom
    return None


# ---------------------------------------------------------------------------
# 跨实例组规则
# ---------------------------------------------------------------------------


def apply_group_rules(
    verdicts: list[InstanceVerdict],
    snapshot: HealthSnapshot,
    th: JudgeThresholds,
) -> list[InstanceVerdict]:
    """组级规则：全渠道断供升级 critical；主渠道故障备渠道顶上 degraded。"""
    by_type: dict[str, list[InstanceVerdict]] = {}
    for verdict in verdicts:
        by_type.setdefault(verdict.task_type, []).append(verdict)

    result: list[InstanceVerdict] = []
    for group in by_type.values():
        updated: dict[str, InstanceVerdict] = {v.source: v for v in group}

        # 全渠道断供：真多渠道组（≥2 个可判定实例）的全部实例当期应跑窗口
        # 均未满足 → 升级 critical。窗口口径天然按交易日历豁免（周末/节假日
        # 无应跑窗口时 windows_without_success=0，不触发）；silent 已是终态级
        # 严重，保留其语义不覆盖；单实例组由单实例「连缺 ≥2 窗」规则负责，
        # 不在组级以 1 个缺失窗口重复升级。
        candidates = [
            v
            for v in group
            if v.status
            not in (STATUS_PAUSED, STATUS_UNCONFIGURED, STATUS_SILENT)
        ]
        if len(candidates) >= 2 and all(
            v.windows_without_success >= 1 for v in candidates
        ):
            for verdict in candidates:
                updated[verdict.source] = replace(
                    verdict,
                    status=STATUS_CRITICAL,
                    reasons=[*verdict.reasons, "该任务类型全渠道断供"],
                )

        # 主渠道故障 → 备渠道顶上（备渠道 healthy → degraded）
        current = list(updated.values())
        primary = next((v for v in current if v.role == "primary"), None)
        if primary is not None and (
            primary.status in (STATUS_CRITICAL, STATUS_SILENT)
            or primary.consecutive_failures >= th.consecutive_failures_degraded
        ):
            for verdict in current:
                if verdict.role == "backup" and verdict.status == STATUS_HEALTHY:
                    updated[verdict.source] = replace(
                        verdict,
                        status=STATUS_DEGRADED,
                        reasons=[*verdict.reasons, "主渠道故障，备渠道顶上"],
                    )
        result.extend(updated.values())
    return result


# ---------------------------------------------------------------------------
# 计划核对（schedule-check）
# ---------------------------------------------------------------------------


@dataclass
class ScheduleCheckRow:
    """单实例某日的计划核对结果。"""

    task_type: str
    source: str
    domain: str
    role: str
    is_active: bool
    has_task_row: bool
    schedule: str | None
    window_total: int = 0
    success_windows: int = 0
    skipped_windows: int = 0
    failed_windows: int = 0
    missing_windows: int = 0
    exempted: bool = False
    last_error_summary: str | None = None
    last_error_cause: str | None = None


def build_schedule_rows(
    facts_list: list[InstanceFacts],
    day_runs: list[RunRow],
    trade_dates: set[date],
    day: date,
    th: JudgeThresholds,
    now_cn: datetime | None = None,
) -> list[ScheduleCheckRow]:
    """按指定 CN 日历日核对每实例「应跑 vs 实跑」（纯函数）。

    非交易日全部标记豁免；交易日按 cron 触发窗口归类
    success / skipped / failed / missing。核对当日时未到期的
    窗口不计入（传 ``now_cn`` 生效），历史日期全量核对。
    """
    runs_by_key: dict[tuple[str, str], list[RunRow]] = {}
    for run in day_runs:
        runs_by_key.setdefault((run.task_type, run.source), []).append(run)

    rows: list[ScheduleCheckRow] = []
    is_trade_day = day in trade_dates
    for facts in facts_list:
        row = ScheduleCheckRow(
            task_type=facts.task_type,
            source=facts.source,
            domain=facts.domain,
            role=facts.role,
            is_active=facts.is_active,
            has_task_row=facts.has_task_row,
            schedule=facts.schedule,
            last_error_summary=facts.last_error_summary,
            last_error_cause=classify_error(facts.last_error_summary),
        )
        if not is_trade_day:
            row.exempted = True
            rows.append(row)
            continue
        grace = _window_grace(facts, _day_aware(day), th)
        deadline = now_cn if now_cn is not None and now_cn.date() == day else None
        instance_runs = runs_by_key.get((facts.task_type, facts.source), [])
        success_times = sorted(_naive_cn(r.started_at) for r in instance_runs if r.status == "success")
        skipped_times = sorted(_naive_cn(r.started_at) for r in instance_runs if r.status == "skipped")
        failed_times = sorted(_naive_cn(r.started_at) for r in instance_runs if r.status in ("failed", "partial"))
        for trigger in day_triggers(facts.schedule or "", day):
            if deadline is not None and trigger + grace > deadline:
                continue
            row.window_total += 1
            if _satisfied(success_times, trigger, grace):
                row.success_windows += 1
            elif _satisfied(skipped_times, trigger, grace):
                row.skipped_windows += 1
            elif _satisfied(failed_times, trigger, grace):
                row.failed_windows += 1
            else:
                row.missing_windows += 1
        rows.append(row)
    return rows


def _day_aware(day: date) -> datetime:
    """把 CN 日历日转成带时区的时刻，供 cron_cadence 做时区换算。"""
    return datetime.combine(day, time.min, tzinfo=CN_TZ)
