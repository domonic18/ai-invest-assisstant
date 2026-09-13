"""采集健康判定引擎单测：覆盖需求 §9 验收样本（纯函数，零 mock）。"""

from datetime import datetime, timezone

import pytest

from app.core.clock import CN_TZ
from app.repositories.admin.collector_health_repository import (
    InstanceConfigRow,
    RunRow,
)
from app.services.collector.health.health_judge import (
    JudgeThresholds,
    apply_group_rules,
    build_schedule_rows,
    judge_instance,
)
from app.services.collector.health.health_service import build_status_values
from app.services.collector.health.health_snapshot import (
    HealthSnapshot,
    InstanceFacts,
    build_instance_facts,
)

pytestmark = pytest.mark.unit

# 2026-09-07(一) ~ 09-11(五)、09-14(一) ~ 09-16(三) 为交易日；周末豁免
_TH = JudgeThresholds()


def _trade_dates() -> set:

    days = []
    for day in range(7, 12):
        days.append(datetime(2026, 9, day).date())
    for day in range(14, 17):
        days.append(datetime(2026, 9, day).date())
    return set(days)


def _cn(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """CN 挂钟时间 → aware UTC（与 DB timestamptz 读取口径一致）。"""
    return datetime(year, month, day, hour, minute, tzinfo=CN_TZ).astimezone(
        timezone.utc
    )


def _run(
    status: str,
    started: datetime,
    *,
    task_type: str = "kline",
    source: str = "sina",
) -> RunRow:
    return RunRow(task_type=task_type, source=source, status=status, started_at=started)


def _facts(**overrides) -> InstanceFacts:
    defaults = dict(
        task_type="kline",
        source="sina",
        domain="kline",
        role="single",
        schedule="30 16 * * 1-5",
        is_active=True,
        has_task_row=True,
        runs=[],
        last_success_at=None,
    )
    defaults.update(overrides)
    return InstanceFacts(**defaults)


def _snapshot(
    instances: list[InstanceFacts],
    checked_cn: datetime,
) -> HealthSnapshot:
    return HealthSnapshot(
        checked_at=checked_cn,
        now_cn_naive=checked_cn.astimezone(CN_TZ).replace(tzinfo=None),
        trade_dates=_trade_dates(),
        instances=instances,
    )


# ---------------------------------------------------------------------------
# §9 样本：静默 / paused / unconfigured
# ---------------------------------------------------------------------------


def test_silent_49_days():
    """实证样本：49 天静默死亡 → silent。"""
    checked = _cn(2026, 9, 16, 8, 30)
    facts = _facts(
        last_success_at=_cn(2026, 7, 29, 16, 30),
        runs=[_run("failed", _cn(2026, 9, 15, 16, 30))],
    )
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "silent"


def test_silent_never_success():
    """回看窗内从未成功 → silent。"""
    checked = _cn(2026, 9, 16, 8, 30)
    facts = _facts(runs=[_run("failed", _cn(2026, 9, 15, 16, 30))])
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "silent"


def test_paused():
    checked = _cn(2026, 9, 16, 8, 30)
    facts = _facts(is_active=False)
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "paused"


def test_unconfigured_channel_without_task_row():
    checked = _cn(2026, 9, 16, 8, 30)
    facts = _facts(has_task_row=False)
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "unconfigured"


# ---------------------------------------------------------------------------
# §9 样本：critical 窗口判定
# ---------------------------------------------------------------------------


def test_critical_two_missed_windows():
    """AI 断产样本：连续应成功窗口无 success → critical。

    检测点 09-16 08:30，日线任务 16:30 的回看期内已到期窗口为
    09-14（宽限 36h）；再往前 09-11 窗口在 4 天回看之外，
    这里用当日多次触发任务验证 ≥2 窗。
    """
    checked = _cn(2026, 9, 16, 8, 30)
    facts = _facts(
        schedule="30 9,16 * * 1-5",  # 一天两场，名义节奏 7h → 宽限 10.5h
        last_success_at=_cn(2026, 9, 10, 16, 30),
        runs=[
            _run("failed", _cn(2026, 9, 15, 16, 30)),
            _run("failed", _cn(2026, 9, 15, 9, 30)),
            _run("failed", _cn(2026, 9, 14, 16, 30)),
            _run("failed", _cn(2026, 9, 14, 9, 30)),
        ],
    )
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "critical"
    assert verdict.windows_without_success >= 2


def test_future_window_not_counted():
    """回归：当日未到期的计划窗口不得计入缺失（08:30 检测 16:30 任务）。"""
    checked = _cn(2026, 9, 16, 8, 30)
    facts = _facts(
        last_success_at=_cn(2026, 9, 15, 16, 31),
        runs=[_run("success", _cn(2026, 9, 15, 16, 31))],
    )
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "healthy"
    assert verdict.windows_without_success == 0


def test_weekend_exempt():
    """周末检测：非交易日不产生应跑窗口，交易日照常满足 → healthy。"""
    checked = _cn(2026, 9, 12, 10, 0)  # 周六
    facts = _facts(
        last_success_at=_cn(2026, 9, 11, 16, 30),
        runs=[
            _run("success", _cn(2026, 9, 11, 16, 30)),
            _run("success", _cn(2026, 9, 10, 16, 30)),
            _run("success", _cn(2026, 9, 9, 16, 30)),
        ],
    )
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "healthy"
    assert verdict.windows_without_success == 0


# ---------------------------------------------------------------------------
# degraded 各触发路径
# ---------------------------------------------------------------------------


def test_degraded_low_7d_rate():
    checked = _cn(2026, 9, 16, 8, 30)
    runs = [_run("success", _cn(2026, 9, 14, 16, 30 + offset)) for offset in range(6)]
    runs += [
        _run("success", _cn(2026, 9, 15, 16, 31)),
        _run("success", _cn(2026, 9, 15, 16, 32)),
        _run("failed", _cn(2026, 9, 15, 16, 33)),
        _run("failed", _cn(2026, 9, 15, 16, 34)),
    ]
    facts = _facts(last_success_at=_cn(2026, 9, 15, 16, 32), runs=runs)
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "degraded"
    assert verdict.success_rate_7d is not None
    assert abs(verdict.success_rate_7d - 0.8) < 1e-9


def test_degraded_consecutive_failures():
    checked = _cn(2026, 9, 16, 8, 30)
    runs = [
        _run("failed", _cn(2026, 9, 15, 16, 33)),
        _run("failed", _cn(2026, 9, 15, 16, 32)),
        _run("failed", _cn(2026, 9, 15, 16, 31)),
        _run("success", _cn(2026, 9, 14, 16, 31)),
    ]
    facts = _facts(last_success_at=_cn(2026, 9, 14, 16, 31), runs=runs)
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "degraded"
    assert verdict.consecutive_failures == 3


def test_degraded_skipped_stall():
    """连续 skipped > 3 阈值 → 产出停滞 degraded（skipped 满足窗口）。"""
    checked = _cn(2026, 9, 16, 8, 30)
    runs = [
        _run("skipped", _cn(2026, 9, 15, 16, 30)),
        _run("skipped", _cn(2026, 9, 14, 16, 30)),
        _run("skipped", _cn(2026, 9, 11, 16, 30)),
        _run("success", _cn(2026, 9, 10, 16, 30)),
    ]
    facts = _facts(last_success_at=_cn(2026, 9, 10, 16, 30), runs=runs)
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "degraded"
    assert any("skipped" in reason for reason in verdict.reasons)


def test_degraded_skipped_stall_counts_weekend_retry():
    """实证样本（stock-daily-analysis）：周末重试 skipped 计入停滞串。

    周四/周五窗口 skipped 后，周六重试又 skipped——非交易日运行是
    真实记录，剔除会漏计停滞串（快照取数已不按交易日过滤 runs）。
    """
    checked = _cn(2026, 9, 13, 15, 0)  # 周日
    runs = [
        _run("skipped", _cn(2026, 9, 13, 10, 10)),  # 周六重试
        _run("skipped", _cn(2026, 9, 11, 16, 40)),
        _run("skipped", _cn(2026, 9, 10, 16, 40)),
        _run("success", _cn(2026, 9, 9, 16, 40)),
    ]
    facts = _facts(last_success_at=_cn(2026, 9, 9, 16, 40), runs=runs)
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.status == "degraded"
    assert any("连续 skipped 3 次" in reason for reason in verdict.reasons)


# ---------------------------------------------------------------------------
# §9 样本：高频任务
# ---------------------------------------------------------------------------


def test_high_frequency_healthy():
    """index-spot 样本：高频任务全日成功 → healthy + 高频标记。"""
    checked = _cn(2026, 9, 16, 8, 30)
    runs = []
    for day in (14, 15):
        for hour in range(9, 16):
            for minute in range(0, 60, 5):
                if hour == 15 and minute > 55:
                    continue
                runs.append(_run("success", _cn(2026, 9, day, hour, minute)))
    facts = _facts(
        schedule="*/5 9-15 * * 1-5",
        last_success_at=runs[-1].started_at,
        runs=runs,
    )
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.is_high_frequency is True
    assert verdict.status == "healthy"


def test_high_frequency_daily_rate_degraded():
    """高频任务最近交易日当日成功率 < 80% → degraded。

    失败与成功交错，所有窗口仍被成功覆盖（不触发 critical 窗口规则），
    仅当日口径触发 degraded。
    """
    checked = _cn(2026, 9, 16, 8, 30)
    runs = []
    for day in (14, 15):
        for minute in range(60):
            if day == 14:
                status = "success"
            else:
                status = "success" if minute % 2 == 1 else "failed"
            runs.append(_run(status, _cn(2026, 9, day, 10, minute)))
    facts = _facts(
        schedule="*/1 10 * * 1-5",
        last_success_at=runs[-1].started_at,
        runs=runs,
    )
    verdict = judge_instance(facts, _snapshot([facts], checked), _TH)
    assert verdict.is_high_frequency is True
    assert verdict.status == "degraded"
    assert verdict.windows_without_success == 0
    assert any("高频" in reason for reason in verdict.reasons)


# ---------------------------------------------------------------------------
# 跨实例组规则
# ---------------------------------------------------------------------------


def test_backup_degraded_when_primary_down():
    """§9 样本：a50 主渠道 critical → 备渠道 degraded（顶上）。"""
    checked = _cn(2026, 9, 16, 8, 30)
    primary = _facts(
        source="sina",
        role="primary",
        schedule="30 9,16 * * 1-5",
        last_success_at=_cn(2026, 9, 10, 16, 30),
        runs=[
            _run("failed", _cn(2026, 9, 15, 16, 30), source="sina"),
            _run("failed", _cn(2026, 9, 15, 9, 30), source="sina"),
            _run("failed", _cn(2026, 9, 14, 16, 30), source="sina"),
        ],
    )
    backup = _facts(
        source="ths",
        role="backup",
        last_error_summary="[ths] Can not decode value starting with character '<'",
        last_success_at=_cn(2026, 9, 15, 16, 31),
        runs=[_run("success", _cn(2026, 9, 15, 16, 31), source="ths")],
    )
    snapshot = _snapshot([primary, backup], checked)
    verdicts = apply_group_rules(
        [judge_instance(primary, snapshot, _TH), judge_instance(backup, snapshot, _TH)],
        snapshot,
        _TH,
    )
    by_source = {v.source: v for v in verdicts}
    assert by_source["sina"].status == "critical"
    assert by_source["ths"].status == "degraded"
    assert any("主渠道" in r for r in by_source["ths"].reasons)
    assert by_source["ths"].last_error_cause == "waf"


def test_group_dead_upgrades_all_to_critical():
    """全渠道断供：多渠道组全部实例当期应跑窗口均未满足 → 升级 critical。"""
    checked = _cn(2026, 9, 16, 8, 30)
    first = _facts(
        source="sina",
        last_success_at=_cn(2026, 9, 11, 16, 30),
        runs=[_run("failed", _cn(2026, 9, 15, 16, 30), source="sina")],
    )
    second = _facts(
        source="ths",
        last_success_at=_cn(2026, 9, 11, 16, 30),
        runs=[_run("failed", _cn(2026, 9, 15, 16, 30), source="ths")],
    )
    snapshot = _snapshot([first, second], checked)
    verdicts = apply_group_rules(
        [judge_instance(first, snapshot, _TH), judge_instance(second, snapshot, _TH)],
        snapshot,
        _TH,
    )
    assert all(v.status == "critical" for v in verdicts)
    assert all(
        any("全渠道断供" in r for r in v.reasons) for v in verdicts
    )


def test_group_dead_not_fired_on_weekend_staleness():
    """周末回看：周五成功的日频任务距上次成功 >24h 属正常脱期豁免，不触发组断供。"""
    checked = _cn(2026, 9, 12, 15, 0)  # 周六 15:00
    first = _facts(
        source="sina",
        last_success_at=_cn(2026, 9, 11, 8, 0),
        runs=[_run("success", _cn(2026, 9, 11, 8, 0), source="sina")],
    )
    second = _facts(
        source="eastmoney",
        last_success_at=_cn(2026, 9, 11, 8, 0),
        runs=[_run("success", _cn(2026, 9, 11, 8, 0), source="eastmoney")],
    )
    snapshot = _snapshot([first, second], checked)
    verdicts = apply_group_rules(
        [judge_instance(first, snapshot, _TH), judge_instance(second, snapshot, _TH)],
        snapshot,
        _TH,
    )
    assert all(v.status == "healthy" for v in verdicts)


def test_group_dead_does_not_override_silent():
    """silent 已是终态级严重：组规则不覆盖（保留 49 天静默语义）。"""
    checked = _cn(2026, 9, 16, 8, 30)
    dead = _facts(source="ths", runs=[])  # 回看窗内从未成功 → silent
    healthy = _facts(
        source="eastmoney",
        last_success_at=_cn(2026, 9, 15, 16, 30),
        runs=[_run("success", _cn(2026, 9, 15, 16, 30), source="eastmoney")],
    )
    snapshot = _snapshot([dead, healthy], checked)
    verdicts = apply_group_rules(
        [judge_instance(dead, snapshot, _TH), judge_instance(healthy, snapshot, _TH)],
        snapshot,
        _TH,
    )
    by_source = {v.source: v for v in verdicts}
    assert by_source["ths"].status == "silent"
    assert by_source["eastmoney"].status == "healthy"


def test_group_dead_skipped_for_single_instance_group():
    """单实例组连缺 1 窗不组级升级（单实例规则连缺 ≥2 窗才 critical）。"""
    checked = _cn(2026, 9, 16, 8, 30)
    solo = _facts(
        source="sina",
        last_success_at=_cn(2026, 9, 11, 16, 30),
        runs=[_run("failed", _cn(2026, 9, 15, 16, 30), source="sina")],
    )
    snapshot = _snapshot([solo], checked)
    verdicts = apply_group_rules(
        [judge_instance(solo, snapshot, _TH)],
        snapshot,
        _TH,
    )
    assert verdicts[0].status == "healthy"


# ---------------------------------------------------------------------------
# 快照组装与落库 diff
# ---------------------------------------------------------------------------


def test_build_instance_facts_roles_and_grouping():
    """主备角色按 priority 分配；清单外日志行（unknown 脏行）不进事实。"""
    universe = [
        InstanceConfigRow(
            task_type="kline", source="sina", schedule="30 16 * * 1-5",
            is_active=True, has_task_row=True, priority=1,
        ),
        InstanceConfigRow(
            task_type="kline", source="ths", schedule="30 16 * * 1-5",
            is_active=True, has_task_row=True, priority=2,
        ),
    ]
    runs = [
        _run("success", _cn(2026, 9, 15, 16, 30), source="sina"),
        _run("failed", _cn(2026, 9, 15, 16, 30), source="unknown"),
    ]
    facts = build_instance_facts(universe, runs, {}, {})
    by_source = {f.source: f for f in facts}
    assert len(facts) == 2
    assert by_source["sina"].role == "primary"
    assert by_source["ths"].role == "backup"
    assert by_source["sina"].runs
    assert all("unknown" not in f.source for f in facts)


def test_build_status_values_state_changed_diff():
    """状态不变不动 state_changed_at；翻转/新实例用本次 checked_at。"""
    from unittest.mock import MagicMock

    checked = _cn(2026, 9, 16, 8, 30)
    old_changed = _cn(2026, 9, 1, 8, 30)

    same = MagicMock()
    same.task_type, same.source, same.status = "kline", "sina", "healthy"
    same.state_changed_at = old_changed
    flipped = MagicMock()
    flipped.task_type, flipped.source, flipped.status = "kline", "ths", "healthy"
    flipped.state_changed_at = old_changed

    from app.services.collector.health.health_judge import InstanceVerdict

    verdicts = [
        InstanceVerdict(task_type="kline", source="sina", status="healthy",
                        role="single", domain="kline"),
        InstanceVerdict(task_type="kline", source="ths", status="critical",
                        role="backup", domain="kline"),
        InstanceVerdict(task_type="quote", source="sina", status="healthy",
                        role="single", domain="quote"),
    ]
    values = build_status_values(verdicts, {("kline", "sina"): same, ("kline", "ths"): flipped}, checked)
    by_key = {(v["task_type"], v["source"]): v for v in values}
    assert by_key[("kline", "sina")]["state_changed_at"] == old_changed
    assert by_key[("kline", "ths")]["state_changed_at"] == checked
    assert by_key[("quote", "sina")]["state_changed_at"] == checked


# ---------------------------------------------------------------------------
# 计划核对（schedule-check）
# ---------------------------------------------------------------------------


def test_schedule_rows_trade_day_and_exempt():
    facts = _facts()
    th = JudgeThresholds()
    # 交易日 09-15：16:30 窗口 success
    rows = build_schedule_rows(
        [facts],
        [_run("success", _cn(2026, 9, 15, 16, 31))],
        _trade_dates(),
        datetime(2026, 9, 15).date(),
        th,
    )
    assert rows[0].window_total == 1
    assert rows[0].success_windows == 1
    assert rows[0].missing_windows == 0
    # 周末豁免
    rows = build_schedule_rows(
        [facts], [], _trade_dates(), datetime(2026, 9, 12).date(), th
    )
    assert rows[0].exempted is True
    assert rows[0].window_total == 0


def test_schedule_rows_today_undue_windows_excluded():
    """核对当日：未到期的窗口不计入 missing。"""
    facts = _facts()
    rows = build_schedule_rows(
        [facts],
        [],
        _trade_dates(),
        datetime(2026, 9, 16).date(),
        JudgeThresholds(),
        now_cn=datetime(2026, 9, 16, 8, 30),
    )
    assert rows[0].window_total == 0
