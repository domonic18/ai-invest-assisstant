"""BaseCollector 基类契约测试（run 流程：采集→转换→校验→计数）。"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector
from collector.spiders.sina_kline import SinaKlineCollector


class DummyCollector(BaseCollector):
    """测试用采集器。"""

    def __init__(self, config: dict, fail_collect: bool = False):
        super().__init__(config)
        self.fail_collect = fail_collect

    async def collect(self, **kwargs) -> list[dict]:
        if self.fail_collect:
            raise ValueError("collect error")
        return [
            {"code": "000001", "value": 10},
            {"code": "000002", "value": 20},
            {"code": "", "value": 30},  # 无效项，由 validate 过滤
        ]

    async def transform(self, raw: dict) -> dict:
        return {"stock_code": raw["code"], "close": raw["value"]}

    async def validate(self, item: dict) -> bool:
        return bool(item.get("stock_code"))


@pytest.mark.unit
class TestBaseCollector:
    def test_result_default_values(self) -> None:
        result = CollectResult(source="test", data_type="dummy", status=CollectStatus.SUCCESS)
        assert result.items_collected == 0
        assert result.items_stored == 0
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_run_success(self) -> None:
        collector = DummyCollector({"source": "test", "data_type": "dummy"})
        result = await collector.run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 3
        assert result.items_stored == 2

    @pytest.mark.asyncio
    async def test_run_failed(self) -> None:
        collector = DummyCollector({"source": "test", "data_type": "dummy"}, fail_collect=True)
        result = await collector.run()

        assert result.status == CollectStatus.FAILED
        assert result.items_collected == 0
        assert result.items_stored == 0
        assert len(result.errors) == 1
        assert "collect error" in result.errors[0]


@pytest.mark.unit
class TestCollectorRun:
    @pytest.mark.asyncio
    async def test_kline_run_with_mocked_collect(self) -> None:
        collector = SinaKlineCollector({"source": "sina", "data_type": "quote_kline_stock_daily"})
        collector.store = AsyncMock(return_value=1)  # type: ignore[method-assign]
        collector.collect = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                {
                    "stock_code": "000001",
                    "trade_date": "2024-01-02",
                    "open": 10.5,
                    "high": 11.0,
                    "low": 10.2,
                    "close": 10.8,
                    "volume": 100000,
                    "amount": 1080000.0,
                    "amplitude": None,
                    "change_pct": None,
                    "turnover_rate": 0.52,
                }
            ]
        )

        result = await collector.run()

        assert result.status.value == "success"
        assert result.items_collected == 1
        assert result.items_stored == 1
        collector.store.assert_awaited_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_fund_flow_run_with_mocked_akshare(self) -> None:
        collector = EastMoneyFundFlowCollector({"source": "eastmoney", "data_type": "fund_flow"})
        mock_df = pd.DataFrame(
            [
                {
                    "股票代码": 1,
                    "股票简称": "Test",
                    "最新价": 10.0,
                    "涨跌幅": 1.0,
                    "换手率": 1.0,
                    "流入资金": "100万",
                    "流出资金": "50万",
                    "净额": "50万",
                    "成交额": "150万",
                }
            ]
        )

        with patch("akshare.stock_fund_flow_individual", return_value=mock_df):
            collector.store = AsyncMock(return_value=1)  # type: ignore[method-assign]
            result = await collector.run(symbols=["000001"])

        assert result.status.value == "success"
        assert result.items_collected == 1
        assert result.items_stored == 1
