"""基础清单与概念映射 spider 契约测试。"""


import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from collector.spiders.sina_stock_list import SinaStockListCollector


def _sw_info(rows: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows)
@pytest.mark.unit
class TestSinaStockListCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list"}
        )
        raw = {
            "stock_code": "600000",
            "stock_name": "浦发银行",
            "market": "sh",
            "full_name": "上海浦东发展银行股份有限公司",
            "industry_level_1": "银行",
            "industry_level_2": "全国性银行",
            "industry_level_3": "股份制银行",
            "listing_date": datetime.date(1999, 11, 10),
            "total_shares": 29352080397,
            "circulating_shares": 29352080397,
            "province": None,
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "600000"
        assert item["industry_level_1"] == "银行"
        assert item["total_shares"] == 29352080397
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_name(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list"}
        )
        item = {"stock_code": "000001", "stock_name": "", "market": "sz"}
        assert await collector.validate(item) is False

    def _patch_akshare(self, components: dict[str, list[str]]):
        base_df = pd.DataFrame(
            [
                {"code": "000001", "name": "平安银行"},
                {"code": "600000", "name": "浦发银行"},
                {"code": "920001", "name": "纬达光电"},
            ]
        )
        sh_df = pd.DataFrame(
            [
                {
                    "证券代码": "600000",
                    "公司全称": "上海浦东发展银行股份有限公司",
                    "上市日期": "1999-11-10",
                }
            ]
        )
        sz_df = pd.DataFrame(
            [
                {
                    "A股代码": "000001",
                    "A股上市日期": "1991-04-03",
                    "A股总股本": "19,405,918,198",
                    "A股流通股本": "19,405,684,991",
                }
            ]
        )
        bj_df = pd.DataFrame(
            [
                {
                    "证券代码": "920001",
                    "总股本": 153656204,
                    "流通股本": 88691020,
                    "上市日期": "2022-12-27",
                    "地区": "江苏省",
                }
            ]
        )
        l1_df = _sw_info([{"行业代码": "801780.SI", "行业名称": "银行"}])
        l2_df = _sw_info(
            [{"行业代码": "801781.SI", "行业名称": "全国性银行", "上级行业": "银行"}]
        )
        l3_df = _sw_info(
            [
                {
                    "行业代码": "859781.SI",
                    "行业名称": "股份制银行",
                    "上级行业": "全国性银行",
                }
            ]
        )

        def _components(symbol: str) -> pd.DataFrame:
            return pd.DataFrame(
                {"证券代码": components.get(symbol, [])}
            )

        return (
            patch("akshare.stock_info_a_code_name", return_value=base_df),
            patch("akshare.stock_info_sh_name_code", return_value=sh_df),
            patch("akshare.stock_info_sz_name_code", return_value=sz_df),
            patch("akshare.stock_info_bj_name_code", return_value=bj_df),
            patch("akshare.sw_index_first_info", return_value=l1_df),
            patch("akshare.sw_index_second_info", return_value=l2_df),
            patch("akshare.sw_index_third_info", return_value=l3_df),
            patch("akshare.index_component_sw", side_effect=_components),
        )

    @pytest.mark.asyncio
    async def test_collect_merges_exchange_details_and_sw_industry(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list", "sw_request_delay": 0}
        )
        components = {"859781": ["000001", "600000"], "801780": ["920001"]}
        patches = self._patch_akshare(components)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
            raw = await collector.collect()

        assert len(raw) == 3
        by_code = {item["stock_code"]: item for item in raw}

        sz = by_code["000001"]
        assert sz["market"] == "sz"
        assert sz["listing_date"] == datetime.date(1991, 4, 3)
        assert sz["total_shares"] == 19405918198
        assert sz["circulating_shares"] == 19405684991
        assert sz["industry_level_1"] == "银行"
        assert sz["industry_level_2"] == "全国性银行"
        assert sz["industry_level_3"] == "股份制银行"

        sh = by_code["600000"]
        assert sh["market"] == "sh"
        assert sh["full_name"] == "上海浦东发展银行股份有限公司"
        assert sh["industry_level_3"] == "股份制银行"

        bj = by_code["920001"]
        assert bj["market"] == "bj"
        assert bj["province"] == "江苏省"
        # 920001 只在 L1 指数中，回退到一级行业
        assert bj["industry_level_1"] == "银行"
        assert bj["industry_level_2"] is None
        assert bj["industry_level_3"] is None

    @pytest.mark.asyncio
    async def test_collect_tolerates_source_failures(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list", "sw_request_delay": 0}
        )
        base_df = pd.DataFrame([{"code": "000001", "name": "平安银行"}])

        with (
            patch("akshare.stock_info_a_code_name", return_value=base_df),
            patch("akshare.stock_info_sh_name_code", side_effect=RuntimeError("boom")),
            patch("akshare.stock_info_sz_name_code", side_effect=RuntimeError("boom")),
            patch("akshare.stock_info_bj_name_code", side_effect=RuntimeError("boom")),
            patch("akshare.sw_index_first_info", side_effect=RuntimeError("boom")),
        ):
            raw = await collector.collect()

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "000001"
        assert raw[0]["market"] == "sz"

    @pytest.mark.asyncio
    async def test_collect_with_requested_symbols(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list", "sw_request_delay": 0}
        )
        patches = self._patch_akshare({"859781": ["600000"]})

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
            raw = await collector.collect(symbols=["600000"])

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "600000"
        assert raw[0]["industry_level_1"] == "银行"

@pytest.mark.unit
class TestEastmoneyConceptConstituentCollector:
    @staticmethod
    def _clist_response(diff: list, total: int) -> MagicMock:
        payload = MagicMock()
        payload.json.return_value = {"data": {"total": total, "diff": diff}}
        return payload

    @pytest.mark.asyncio
    async def test_collect_maps_concepts_and_members(self) -> None:
        from collector.spiders import eastmoney_concept_constituents as spider_mod

        collector = spider_mod.EastmoneyConceptConstituentCollector(
            {"source": "eastmoney", "data_type": "mapping_stock_concept"}
        )
        responses = [
            # 概念列表：单页即取满（len(rows) >= total），覆盖分页终止条件
            self._clist_response(
                [{"f12": "BK0816", "f14": "稀土永磁"}, {"f12": "BK1000", "f14": "测试概念"}],
                total=2,
            ),
            # BK0816 成分：含一个非纯数字代码（应被过滤）
            self._clist_response(
                [{"f12": "600111", "f14": "北方稀土"}, {"f12": "HK00700", "f14": "腾讯控股"}],
                total=2,
            ),
            self._clist_response(
                [{"f12": "000001", "f14": "平安银行"}, {"f12": "600000", "f14": "浦发银行"}],
                total=2,
            ),
        ]
        urls: list[str] = []

        def fake_get(url: str, params: dict, **kwargs: object) -> MagicMock:
            urls.append(url)
            return responses.pop(0)

        with patch.object(spider_mod, "eastmoney_get_chrome", fake_get):
            items = await collector.collect()

        assert items == [
            {
                "stock_code": "600111",
                "concept_code": "BK0816",
                "concept_name": "稀土永磁",
                "source": "eastmoney",
            },
            {
                "stock_code": "000001",
                "concept_code": "BK1000",
                "concept_name": "测试概念",
                "source": "eastmoney",
            },
            {
                "stock_code": "600000",
                "concept_code": "BK1000",
                "concept_name": "测试概念",
                "source": "eastmoney",
            },
        ]
        assert responses == []  # 全部请求均已消费
        # clist 固定走 push2delay 镜像主机（push2 会被高频连发封禁）
        assert urls and all(u.startswith("https://push2delay.eastmoney.com/") for u in urls)

    @pytest.mark.asyncio
    async def test_collect_raises_when_concept_list_fails(self) -> None:
        from collector.spiders import eastmoney_concept_constituents as spider_mod

        collector = spider_mod.EastmoneyConceptConstituentCollector(
            {"source": "eastmoney", "data_type": "mapping_stock_concept"}
        )
        with patch.object(
            spider_mod, "eastmoney_get_chrome", MagicMock(side_effect=ConnectionError("boom"))
        ):
            with pytest.raises(RuntimeError, match="获取东方财富概念列表失败"):
                await collector.collect()

    @pytest.mark.asyncio
    async def test_collect_raises_when_member_fetch_fails(self) -> None:
        """单概念成员拉取失败必须整体失败重试，禁止残缺映射入库。"""
        from collector.spiders import eastmoney_concept_constituents as spider_mod

        collector = spider_mod.EastmoneyConceptConstituentCollector(
            {"source": "eastmoney", "data_type": "mapping_stock_concept"}
        )
        responses = [
            self._clist_response([{"f12": "BK0816", "f14": "稀土永磁"}], total=1),
            ConnectionError("Remote end closed connection without response"),
        ]

        def fake_get(url: str, params: dict, **kwargs: object) -> MagicMock:
            return responses.pop(0)

        with patch.object(spider_mod, "eastmoney_get_chrome", fake_get):
            with pytest.raises(RuntimeError, match="概念成分拉取失败 1/1"):
                await collector.collect()
