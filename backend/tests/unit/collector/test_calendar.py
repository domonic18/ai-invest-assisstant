"""交易日历与快照/日期类 spider 非交易日守卫的单元测试。"""

import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from collector.core import calendar
from collector.spiders.eastmoney_broken_pool import EastmoneyBrokenPoolCollector
from collector.spiders.eastmoney_limit_up_pool import EastMoneyLimitUpPoolCollector
from collector.spiders.sina_market_breadth import SinaMarketBreadthCollector


@pytest.mark.unit
class TestTradeCalendar:
    def test_is_trading_day_all_days_seeded(self) -> None:
        # conftest 播种 2026 全年每天均为交易日
        assert calendar.is_trading_day(datetime.date(2026, 7, 17)) is True

    def test_is_trading_day_weekend_fallback_beyond_range(self) -> None:
        # 超出日历范围（2027 年）回退工作日启发式
        assert calendar.is_trading_day(datetime.date(2027, 1, 2)) is False  # 周六
        assert calendar.is_trading_day(datetime.date(2027, 1, 4)) is True  # 周一

    def test_latest_trading_day(self) -> None:
        assert calendar.latest_trading_day(datetime.date(2026, 7, 19)) == (
            datetime.date(2026, 7, 19)
        )


@pytest.mark.unit
class TestLimitUpPoolTradingDayGuard:
    @pytest.mark.asyncio
    async def test_returns_empty_on_non_trading_day(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
        )
        with (
            patch(
                "collector.spiders.eastmoney_limit_up_pool.is_trading_day",
                return_value=False,
            ),
            patch("akshare.stock_zt_pool_em") as mock_api,
        ):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 19))

        assert raw == []
        mock_api.assert_not_called()

    @pytest.mark.asyncio
    async def test_trading_day_still_collects(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
        )
        df = pd.DataFrame(
            [{"代码": "002338", "名称": "奥普光电", "涨跌幅": 10.01, "连板数": 6}]
        )
        with patch("akshare.stock_zt_pool_em", return_value=df):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert len(raw) == 1
        assert raw[0]["trade_date"] == datetime.date(2026, 7, 17)


@pytest.mark.unit
class TestBrokenPoolTradingDayGuard:
    @pytest.mark.asyncio
    async def test_returns_empty_on_non_trading_day(self) -> None:
        collector = EastmoneyBrokenPoolCollector(
            {"source": "eastmoney", "data_type": "broken-pool"}
        )
        with (
            patch(
                "collector.spiders.eastmoney_broken_pool.is_trading_day",
                return_value=False,
            ),
            patch("akshare.stock_zt_pool_zbgc_em") as mock_api,
        ):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 19))

        assert raw == []
        mock_api.assert_not_called()


@pytest.mark.unit
class TestMarketBreadthSnapshotGuard:
    @pytest.mark.asyncio
    async def test_rejects_date_other_than_latest_trading_day(self) -> None:
        collector = SinaMarketBreadthCollector(
            {"source": "sina", "data_type": "market-breadth"}
        )
        with (
            patch(
                "collector.spiders.sina_market_breadth.latest_trading_day",
                return_value=datetime.date(2026, 7, 20),
            ),
            patch("akshare.stock_zh_a_spot") as mock_api,
        ):
            # 显式请求历史日期：快照接口无法满足，必须拒绝
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert raw == []
        mock_api.assert_not_called()
