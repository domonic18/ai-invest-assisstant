"""app.core.clock 时段谓词边界测试（批次 8 盘中执行门控）。

纯时钟谓词不判交易日（周末/节假日由调用方保证），此处钉死 A 股
连续竞价与尾盘强检窗口的分钟级边界。
"""

from datetime import datetime, timezone

import pytest

from app.core.clock import CN_TZ, in_tail_check_window, in_trading_session


def _cn(hour: int, minute: int) -> datetime:
    """北京时间 aware datetime（谓词入参）。"""
    return datetime(2026, 9, 29, hour, minute, tzinfo=CN_TZ)


@pytest.mark.unit
class TestInTradingSession:
    def test_before_open(self) -> None:
        assert not in_trading_session(_cn(9, 29))

    def test_open_boundary_inclusive(self) -> None:
        assert in_trading_session(_cn(9, 30))

    def test_morning_session(self) -> None:
        assert in_trading_session(_cn(10, 0))
        assert in_trading_session(_cn(11, 29))

    def test_morning_close_exclusive(self) -> None:
        assert not in_trading_session(_cn(11, 30))

    def test_lunch_break(self) -> None:
        assert not in_trading_session(_cn(12, 30))

    def test_afternoon_session(self) -> None:
        assert in_trading_session(_cn(13, 0))
        assert in_trading_session(_cn(14, 59))

    def test_afternoon_close_exclusive(self) -> None:
        assert not in_trading_session(_cn(15, 0))

    def test_after_close(self) -> None:
        assert not in_trading_session(_cn(16, 0))

    def test_utc_input_normalized(self) -> None:
        """非北京时间入参按 astimezone 归一：UTC 01:30 = 北京 09:30。"""
        utc_input = datetime(2026, 9, 29, 1, 30, tzinfo=timezone.utc)
        assert in_trading_session(utc_input)


@pytest.mark.unit
class TestInTailCheckWindow:
    def test_before_window(self) -> None:
        assert not in_tail_check_window(_cn(14, 49))

    def test_window_start_inclusive(self) -> None:
        assert in_tail_check_window(_cn(14, 50))

    def test_window_end_exclusive(self) -> None:
        assert not in_tail_check_window(_cn(15, 0))

    def test_morning_not_in_window(self) -> None:
        assert not in_tail_check_window(_cn(10, 0))
