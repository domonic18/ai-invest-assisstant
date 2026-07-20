"""Collector 单元测试公共 fixture。"""

from datetime import date, timedelta

import pytest

import collector.core.calendar as calendar


@pytest.fixture(autouse=True)
def _stub_trade_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    """播种进程内交易日历缓存，避免测试触发真实网络请求。

    2026 全年每一天都视为交易日（保持既有测试的历史行为）；
    需要验证非交易日守卫的用例应显式 patch spider 模块内的
    is_trading_day / latest_trading_day。
    """
    dates = frozenset(date(2026, 1, 1) + timedelta(days=i) for i in range(365))
    monkeypatch.setattr(
        calendar, "_cache", (dates, date(2026, 12, 31), date(2099, 1, 1))
    )
