"""股池 spider 契约测试。"""


import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from collector.spiders.eastmoney_broken_pool import EastmoneyBrokenPoolCollector
from collector.spiders.eastmoney_limit_down_pool import (
    EastmoneyLimitDownPoolCollector,
)
from collector.spiders.eastmoney_limit_up_pool import EastMoneyLimitUpPoolCollector


@pytest.mark.unit
class TestEastMoneyLimitUpPoolCollector:
    @pytest.mark.asyncio
    async def test_collect_maps_akshare_columns(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "序号": 1,
                    "代码": "002338",
                    "名称": "奥普光电",
                    "涨跌幅": 10.01,
                    "最新价": 25.6,
                    "成交额": 3.5e8,
                    "流通市值": 1.2e10,
                    "总市值": 1.3e10,
                    "换手率": 9.8,
                    "封板资金": 4.2e8,
                    "首次封板时间": "092500",
                    "最后封板时间": "135900",
                    "炸板次数": 2,
                    "涨停统计": "6/6",
                    "连板数": 6,
                    "所属行业": "光学光电子",
                }
            ]
        )
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
        )
        with patch("akshare.stock_zt_pool_em", return_value=df):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "002338"
        assert raw[0]["consecutive_boards"] == 6
        assert raw[0]["sealed_amount"] == 4.2e8
        assert raw[0]["industry"] == "光学光电子"

    @pytest.mark.asyncio
    async def test_collect_empty_pool(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
        )
        with patch("akshare.stock_zt_pool_em", return_value=pd.DataFrame()):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert raw == []

    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
        )
        raw = {
            "trade_date": datetime.date(2026, 7, 17),
            "stock_code": "002338",
            "stock_name": "奥普光电",
            "change_pct": 10.01,
            "latest_price": 25.6,
            "turnover_rate": 9.8,
            "sealed_amount": 4.2e8,
            "first_seal_time": "092500",
            "last_seal_time": "135900",
            "broken_limit_count": 2,
            "limit_status": "6/6",
            "consecutive_boards": 6,
            "industry": "光学光电子",
        }
        item = await collector.transform(raw)
        assert item["source"] == "eastmoney"
        assert item["consecutive_boards"] == 6
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_code(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
        )
        assert await collector.validate(
            {"trade_date": datetime.date(2026, 7, 17), "stock_code": None}
        ) is False


@pytest.mark.unit
class TestEastmoneyBrokenPoolCollector:
    @pytest.mark.asyncio
    async def test_collect_counts_broken_pool(self) -> None:
        collector = EastmoneyBrokenPoolCollector(
            {"source": "eastmoney", "data_type": "broken-pool"}
        )
        mock_df = pd.DataFrame({"代码": ["000001", "000002", "000003"]})
        with patch("akshare.stock_zt_pool_zbgc_em", return_value=mock_df):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert raw == [
            {"trade_date": datetime.date(2026, 7, 17), "broken_limit_count": 3}
        ]

    @pytest.mark.asyncio
    async def test_collect_error_returns_empty(self) -> None:
        collector = EastmoneyBrokenPoolCollector(
            {"source": "eastmoney", "data_type": "broken-pool"}
        )
        with patch("akshare.stock_zt_pool_zbgc_em", side_effect=ValueError("x")):
            assert await collector.collect(
                trade_date=datetime.date(2026, 7, 17)
            ) == []


@pytest.mark.unit
class TestEastmoneyLimitDownPoolCollector:
    @pytest.mark.asyncio
    async def test_collect_counts_limit_down_pool(self) -> None:
        collector = EastmoneyLimitDownPoolCollector(
            {"source": "eastmoney", "data_type": "limit-down-pool"}
        )
        mock_df = pd.DataFrame({"代码": ["000001", "000002"]})
        with patch("akshare.stock_zt_pool_dtgc_em", return_value=mock_df):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert raw == [
            {"trade_date": datetime.date(2026, 7, 17), "limit_down_count": 2}
        ]

    @pytest.mark.asyncio
    async def test_collect_error_returns_empty(self) -> None:
        collector = EastmoneyLimitDownPoolCollector(
            {"source": "eastmoney", "data_type": "limit-down-pool"}
        )
        with patch("akshare.stock_zt_pool_dtgc_em", side_effect=ValueError("x")):
            assert await collector.collect(
                trade_date=datetime.date(2026, 7, 17)
            ) == []

    @pytest.mark.asyncio
    async def test_collect_skips_non_trading_day(self) -> None:
        collector = EastmoneyLimitDownPoolCollector(
            {"source": "eastmoney", "data_type": "limit-down-pool"}
        )
        with (
            patch(
                "collector.spiders.eastmoney_limit_down_pool.is_trading_day",
                return_value=False,
            ),
            patch(
                "akshare.stock_zt_pool_dtgc_em",
                side_effect=AssertionError("不应请求接口"),
            ),
        ):
            assert await collector.collect(
                trade_date=datetime.date(2026, 7, 19)
            ) == []
