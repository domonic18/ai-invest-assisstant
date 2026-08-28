"""collector cron 解析工具契约测试（Celery crontab 语义）。

Celery crontab 星期数字约定与标准 cron 一致（0/7=周日、1=周一），
``_parse_cron`` 必须原样透传星期字段——任何转换都会使调度整体偏移一天。
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from celery.schedules import crontab

from collector.core.cron import _normalize_cron_field, _parse_cron

_CN = ZoneInfo("Asia/Shanghai")


def _build_crontab(schedule: str) -> crontab:
    parsed = _parse_cron(schedule)
    return crontab(
        minute=_normalize_cron_field(parsed["minute"]),
        hour=_normalize_cron_field(parsed["hour"]),
        day_of_month=parsed["day"],
        month_of_year=parsed["month"],
        day_of_week=parsed["day_of_week"],
    )


def _next_from(schedule: str, after_cst: datetime) -> datetime:
    """返回 schedule 在 after_cst（北京时间 aware）之后的下次触发（UTC aware）。"""
    after_utc = after_cst.astimezone(timezone.utc)
    return after_utc + _build_crontab(schedule).remaining_estimate(after_utc)


@pytest.mark.unit
class TestNormalizeCronField:
    def test_step_only_normalized(self) -> None:
        assert _normalize_cron_field("0/30") == "*/30"

    def test_range_with_step_unchanged(self) -> None:
        assert _normalize_cron_field("2-57/5") == "2-57/5"

    def test_asterisk_unchanged(self) -> None:
        assert _normalize_cron_field("*") == "*"


@pytest.mark.unit
class TestParseCron:
    def test_weekday_passthrough(self) -> None:
        parsed = _parse_cron("*/5 9-15 * * 1-5")
        assert parsed["day_of_week"] == "1-5"
        assert parsed["minute"] == "*/5"
        assert parsed["hour"] == "9-15"
        assert parsed["day"] == "*"
        assert parsed["month"] == "*"

    def test_invalid_expression(self) -> None:
        with pytest.raises(ValueError, match="Invalid cron expression"):
            _parse_cron("*/5 9-15 *")


@pytest.mark.unit
class TestCeleryWeekdaySemantics:
    def test_weekday_schedule_skips_weekend(self) -> None:
        """1-5（周一至周五）的调度不应在周六触发。"""
        # 2026-07-18 12:00 北京时间 = 周六
        saturday = datetime(2026, 7, 18, 12, 0, tzinfo=_CN)
        nxt = _next_from("*/5 9-15 * * 1-5", saturday).astimezone(_CN)
        assert nxt.weekday() == 0  # 下一次触发是周一
        assert (nxt.hour, nxt.minute) == (9, 0)

    def test_saturday_schedule_fires_on_saturday(self) -> None:
        # 2026-07-17 12:00 北京时间 = 周五
        friday = datetime(2026, 7, 17, 12, 0, tzinfo=_CN)
        nxt = _next_from("0 2 * * 6", friday).astimezone(_CN)
        assert nxt.weekday() == 5  # 周六
        assert (nxt.hour, nxt.minute) == (2, 0)

    def test_friday_evening_next_fire_is_monday(self) -> None:
        """周五收盘批之后的下次触发应为下周一，而非周日。"""
        # 2026-08-28 18:57 北京时间 = 周五
        friday = datetime(2026, 8, 28, 18, 57, tzinfo=_CN)
        nxt = _next_from("0 16 * * 1-5", friday).astimezone(_CN)
        assert nxt.weekday() == 0  # 周一
        assert (nxt.hour, nxt.minute) == (16, 0)
