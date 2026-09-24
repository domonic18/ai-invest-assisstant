"""资金流 spider 契约测试。"""


import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector
from collector.spiders.eastmoney_sector_fund_flow import (
    EastMoneySectorFundFlowCollector,
)
from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector


@pytest.mark.unit
class TestEastMoneyFundFlowCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = EastMoneyFundFlowCollector({"source": "eastmoney", "data_type": "fund_flow"})
        raw = {
            "stock_code": "000001",
            "trade_date": datetime.date(2024, 1, 2),
            "main_net_inflow": 1_000_000.0,
            "super_large_net": 500_000.0,
            "large_net": 500_000.0,
            "medium_net": -300_000.0,
            "small_net": -700_000.0,
        }
        item = await collector.transform(raw)
        assert item["main_net_inflow"] == 1_000_000.0
        assert item["small_net"] == -700_000.0
        assert await collector.validate(item) is True


@pytest.mark.unit
class TestEastMoneySectorFundFlowCollector:
    @pytest.mark.asyncio
    async def test_collect_maps_push2_fields(self) -> None:
        rows = [
            {
                "f12": "BK1036",
                "f14": "半导体",
                "f3": 4.2,
                "f62": 2.26e9,
                "f66": 1.5e9,
                "f72": 7.6e8,
                "f78": -3e8,
                "f84": -1.9e9,
                "f204": "北方华创",
                "f205": "002371",
            }
        ]
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
        )
        with patch.object(collector, "_fetch_rank", return_value=rows):
            raw = await collector.collect(sector_type="industry")

        assert len(raw) == 1
        assert raw[0]["sector_name"] == "半导体"
        assert raw[0]["sector_code"] == "BK1036"
        assert raw[0]["change_pct"] == 4.2
        assert raw[0]["main_net_inflow"] == 2.26e9
        assert raw[0]["top_stock_name"] == "北方华创"
        assert raw[0]["top_stock_code"] == "002371"

        item = await collector.transform(raw[0])
        assert item["change_pct"] == 4.2
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_collect_without_type_covers_both_types(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
        )
        rows = [
            {"f12": "BK1036", "f14": "半导体", "f3": 4.2, "f62": 2.26e9,
             "f66": 1.5e9, "f72": 7.6e8, "f78": -3e8, "f84": -1.9e9,
             "f204": "北方华创", "f205": "002371"},
        ]
        with patch.object(collector, "_fetch_rank", return_value=rows) as rank:
            raw = await collector.collect()

        assert rank.call_count == 2
        assert [r["sector_type"] for r in raw] == ["industry", "concept"]
        assert all(r["sector_name"] == "半导体" for r in raw)

    def test_fetch_rank_paginates(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
        )
        pages = [
            {"total": 3, "diff": [{"f14": "板块A"}, {"f14": "板块B"}]},
            {"total": 3, "diff": [{"f14": "板块C"}]},
        ]
        with (
            patch(
                "collector.spiders.eastmoney_sector_fund_flow._PAGE_SIZE", 2
            ),
            patch.object(
                collector, "_request_page", side_effect=pages
            ) as request_page,
        ):
            rows = collector._fetch_rank("industry")

        assert [row["f14"] for row in rows] == ["板块A", "板块B", "板块C"]
        assert request_page.call_count == 2
        assert request_page.call_args_list[1].args[0]["pn"] == 2

    @pytest.mark.asyncio
    async def test_collect_history_picks_target_date_row(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
        )
        boards = [{"f12": "BK0420", "f14": "航空机场"}]
        klines = [
            "2026-07-16,100.0,10.0,20.0,30.0,40.0,1.5",
            "2026-07-17,-162370288.0,292831632.0,-130461344.0,-133406864.0,-28963424.0,-0.88",
        ]
        with (
            patch.object(collector, "_fetch_rank", return_value=boards),
            patch.object(collector, "_fetch_daykline", return_value=klines),
        ):
            raw = await collector.collect(
                sector_type="industry", trade_date=datetime.date(2026, 7, 17)
            )

        assert len(raw) == 1
        item = raw[0]
        assert item["sector_code"] == "BK0420"
        assert item["trade_date"] == datetime.date(2026, 7, 17)
        assert item["main_net_inflow"] == -162370288.0
        assert item["small_net"] == 292831632.0
        assert item["medium_net"] == -130461344.0
        assert item["large_net"] == -133406864.0
        assert item["super_large_net"] == -28963424.0
        assert item["change_pct"] == -0.88
        assert item["top_stock_name"] is None
        assert await collector.validate(await collector.transform(item)) is True

    @pytest.mark.asyncio
    async def test_collect_history_skips_non_trading_day(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
        )
        with (
            patch(
                "collector.spiders.eastmoney_sector_fund_flow.is_trading_day",
                return_value=False,
            ),
            patch.object(
                collector, "_fetch_rank", side_effect=AssertionError("不应请求网络")
            ),
        ):
            raw = await collector.collect(
                sector_type="industry", trade_date=datetime.date(2026, 7, 19)
            )

        assert raw == []

    def test_request_page_uses_shared_eastmoney_client(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
        )
        response = MagicMock()
        response.json.return_value = {"data": {"total": 0, "diff": []}}
        with patch(
            "collector.spiders.eastmoney_sector_fund_flow.eastmoney_get_chrome",
            return_value=response,
        ) as get:
            data = collector._request_page({"pn": 1})

        assert data == {"total": 0, "diff": []}
        assert (
            get.call_args.args[0]
            == "https://push2delay.eastmoney.com/api/qt/clist/get"
        )
        assert get.call_args.kwargs["params"] == {"pn": 1}


@pytest.mark.unit
class TestThsSectorFundFlowCollector:
    def _make_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "序号": 1,
                    "行业": "酿酒行业",
                    "行业指数": 3800.5,
                    "行业-涨跌幅": 1.23,
                    "流入资金": "10.5亿",
                    "流出资金": "9.5亿",
                    "净额": "1.23亿",
                    "公司家数": 37,
                    "领涨股": "贵州茅台",
                    "领涨股-涨跌幅": 2.5,
                    "当前价": 1680.0,
                },
                {
                    "序号": 2,
                    "行业": "银行",
                    "行业指数": 3200.0,
                    "行业-涨跌幅": -0.5,
                    "流入资金": "5000万",
                    "流出资金": "6000万",
                    "净额": -3.15,
                    "公司家数": 42,
                    "领涨股": "招商银行",
                    "领涨股-涨跌幅": 0.8,
                    "当前价": 35.0,
                },
            ]
        )

    @pytest.mark.asyncio
    async def test_collect_maps_ths_fields(self) -> None:

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "capital_fund_flow_sector"}
        )
        with patch(
            "akshare.stock_fund_flow_industry", return_value=self._make_df()
        ):
            raw = await collector.collect(sector_type="industry")

        assert len(raw) == 2
        first = raw[0]
        assert first["sector_code"] == "酿酒行业"
        assert first["sector_name"] == "酿酒行业"
        assert first["sector_type"] == "industry"
        assert first["change_pct"] == 1.23
        assert first["main_net_inflow"] == 1.23 * 100_000_000
        assert first["super_large_net"] is None
        assert first["top_stock_name"] == "贵州茅台"
        assert raw[1]["main_net_inflow"] == -3.15 * 100_000_000

    @pytest.mark.asyncio
    async def test_collect_concept_maps_ths_fields(self) -> None:

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "capital_fund_flow_sector"}
        )
        with patch(
            "akshare.stock_fund_flow_concept", return_value=self._make_df()
        ):
            raw = await collector.collect(sector_type="concept")

        assert len(raw) == 2
        first = raw[0]
        assert first["sector_code"] == "酿酒行业"
        assert first["sector_name"] == "酿酒行业"
        assert first["sector_type"] == "concept"
        assert first["change_pct"] == 1.23
        assert first["main_net_inflow"] == 1.23 * 100_000_000
        assert first["top_stock_name"] == "贵州茅台"

    @pytest.mark.asyncio
    async def test_collect_rejects_unsupported_sector_type(self) -> None:

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "capital_fund_flow_sector"}
        )
        with pytest.raises(ValueError, match="仅支持行业/概念板块"):
            await collector.collect(sector_type="region")

    @pytest.mark.asyncio
    async def test_validate(self) -> None:

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "capital_fund_flow_sector"}
        )
        item = {
            "sector_code": "酿酒行业",
            "sector_name": "酿酒行业",
            "trade_date": datetime.date.today(),
        }
        assert await collector.validate(item) is True
        assert await collector.validate({**item, "sector_name": None}) is False
