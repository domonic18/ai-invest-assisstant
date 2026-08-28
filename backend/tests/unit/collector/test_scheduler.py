"""collector cron 解析工具契约测试。"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from apscheduler.triggers.cron import CronTrigger

from collector.core.cron import SCHEDULER_TZ, _convert_day_of_week, _parse_cron


@pytest.mark.unit
class TestConvertDayOfWeek:
    @pytest.mark.parametrize(
        ("expr", "expected"),
        [
            ("*", "*"),
            ("1-5", "0-4"),  # 周一~周五
            ("6", "5"),  # 周六
            ("0", "6"),  # 周日
            ("7", "6"),  # 周日（另一种写法）
            ("1,3,5", "0,2,4"),
            ("0-6", "0,1,2,3,4,5,6"),  # 整周回绕展开
            ("mon-fri", "mon-fri"),  # 名称原样保留
            ("*/2", "*/2"),
        ],
    )
    def test_mapping(self, expr: str, expected: str) -> None:
        assert _convert_day_of_week(expr) == expected


@pytest.mark.unit
class TestParseCron:
    def test_weekday_conversion(self) -> None:
        parsed = _parse_cron("*/5 9-15 * * 1-5")
        assert parsed["day_of_week"] == "0-4"
        assert parsed["minute"] == "*/5"
        assert parsed["hour"] == "9-15"

    def test_invalid_expression(self) -> None:
        with pytest.raises(ValueError, match="Invalid cron expression"):
            _parse_cron("*/5 9-15 *")

    def test_saturday_not_fired_for_weekday_schedule(self) -> None:
        """1-5（周一至周五）的调度不应在周六触发。"""
        parsed = _parse_cron("*/5 9-15 * * 1-5")
        trigger = CronTrigger(timezone=SCHEDULER_TZ, **parsed)
        # 2026-07-18 12:00 北京时间 = 周六
        saturday = datetime(2026, 7, 18, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        nxt = trigger.get_next_fire_time(None, saturday)
        assert nxt is not None
        assert nxt.weekday() == 0  # 下一次触发是周一

    def test_saturday_schedule_fires_on_saturday(self) -> None:
        parsed = _parse_cron("0 2 * * 6")
        trigger = CronTrigger(timezone=SCHEDULER_TZ, **parsed)
        friday = datetime(2026, 7, 17, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        nxt = trigger.get_next_fire_time(None, friday)
        assert nxt is not None
        assert nxt.weekday() == 5  # 周六
        assert (nxt.hour, nxt.minute) == (2, 0)

    def test_timezone_is_beijing(self) -> None:
        parsed = _parse_cron("35 15 * * 1-5")
        trigger = CronTrigger(timezone=SCHEDULER_TZ, **parsed)
        # 2026-07-20 10:00 北京时间 = 周一
        monday = datetime(2026, 7, 20, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        nxt = trigger.get_next_fire_time(None, monday)
        assert nxt is not None
        assert (nxt.hour, nxt.minute) == (15, 35)
        assert nxt.utcoffset().total_seconds() == 8 * 3600
