"""EastMoney 研报采集器契约测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.spiders.eastmoney_research_report import (
    EastMoneyResearchReportCollector,
    _map_entry,
)

# 实测 reportapi 返回结构（2026-07-24）
_LIST_ITEM = {
    "title": "北交所首次覆盖报告：FPC整线小巨人",
    "stockName": "锐翔智能",
    "stockCode": "920178",
    "orgSName": "开源证券",
    "publishDate": "2026-07-24 00:00:00.000",
    "infoCode": "AP202607241827321448",
    "predictNextYearEps": "3.26",
    "predictNextYearPe": "47.5",
    "predictThisYearEps": "2.45",
    "predictThisYearPe": "63.4",
    "indvInduName": "自动化设备",
    "emRatingName": "增持",
    "ratingChange": 2,
    "researcher": "诸海滨",
    "indvAimPriceT": "58.0",
    "indvAimPriceL": "45.0",
    "attachPages": 29,
}


def _collector() -> EastMoneyResearchReportCollector:
    return EastMoneyResearchReportCollector(
        {"source": "eastmoney", "data_type": "research_report"}
    )


@pytest.mark.unit
class TestMapEntry:
    def test_maps_all_fields(self) -> None:
        entry = _map_entry(dict(_LIST_ITEM))
        assert entry is not None
        assert entry["stock_code"] == "920178"
        assert entry["title"] == _LIST_ITEM["title"]
        assert entry["publish_date"].date().isoformat() == "2026-07-24"
        assert entry["source_url"] == (
            "https://pdf.dfcfw.com/pdf/H3_AP202607241827321448_1.pdf"
        )
        assert entry["industry_tags"] == ["自动化设备"]
        extra = entry["extra"]
        assert extra["stock_name"] == "锐翔智能"
        assert extra["broker"] == "开源证券"
        assert extra["rating"] == "增持"
        assert extra["rating_change"] == 2
        assert extra["author"] == "诸海滨"
        assert extra["eps_forecast"] == {"this_year": 2.45, "next_year": 3.26}
        assert extra["pe_forecast"] == {"this_year": 63.4, "next_year": 47.5}
        assert extra["aim_price_high"] == 58.0
        assert extra["aim_price_low"] == 45.0
        assert extra["pages"] == 29
        assert extra["info_code"] == "AP202607241827321448"

    def test_returns_none_without_info_code(self) -> None:
        item = dict(_LIST_ITEM)
        item["infoCode"] = ""
        assert _map_entry(item) is None

    def test_tolerates_empty_forecasts(self) -> None:
        item = dict(_LIST_ITEM)
        item["predictThisYearEps"] = ""
        item["indvAimPriceT"] = ""
        entry = _map_entry(item)
        assert entry is not None
        assert entry["extra"]["eps_forecast"]["this_year"] is None
        assert entry["extra"]["aim_price_high"] is None


@pytest.mark.unit
class TestCollect:
    @pytest.mark.asyncio
    async def test_collect_fetches_list_and_pdfs(self) -> None:
        pdf_bytes = b"%PDF-1.4 fake pdf"

        list_response = MagicMock()
        list_response.json.return_value = {
            "hits": 1,
            "data": [dict(_LIST_ITEM)],
            "TotalPage": 1,
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=list_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch(
                "collector.spiders.eastmoney_research_report.download_research_pdf",
                AsyncMock(return_value=pdf_bytes),
            ),
        ):
            raw = await _collector().collect(
                start_date="2026-07-24", end_date="2026-07-24"
            )

        assert len(raw) == 1
        assert raw[0]["file_bytes"] == pdf_bytes
        assert raw[0]["file_size"] == len(pdf_bytes)
        assert raw[0]["source_url"].endswith("_1.pdf")

    @pytest.mark.asyncio
    async def test_collect_keeps_entry_when_pdf_download_fails(self) -> None:
        list_response = MagicMock()
        list_response.json.return_value = {
            "hits": 1,
            "data": [dict(_LIST_ITEM)],
            "TotalPage": 1,
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=list_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch(
                "collector.spiders.eastmoney_research_report.download_research_pdf",
                AsyncMock(side_effect=ValueError("not a PDF payload")),
            ),
        ):
            raw = await _collector().collect(
                start_date="2026-07-24", end_date="2026-07-24"
            )

        assert len(raw) == 1
        assert raw[0]["file_bytes"] is None


@pytest.mark.unit
class TestTransformValidate:
    @pytest.mark.asyncio
    async def test_transform_output_passes_validate_without_pdf(self) -> None:
        collector = _collector()
        entry = _map_entry(dict(_LIST_ITEM))
        assert entry is not None
        transformed = await collector.transform(entry)
        assert transformed["doc_type"] == "research"
        assert transformed["source"] == "eastmoney"
        assert await collector.validate(transformed)

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_fields(self) -> None:
        collector = _collector()
        assert not await collector.validate({"stock_code": "920178"})
        assert not await collector.validate(
            {
                "stock_code": "920178",
                "title": "t",
                "publish_date": None,
                "source_url": "u",
            }
        )
