"""资讯 spider 契约测试。"""


import datetime

import pytest

from collector.spiders.sina_news import SinaNewsCollector


@pytest.mark.unit
class TestSinaNewsCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaNewsCollector({"source": "sina", "data_type": "news"})
        raw = {
            "stock_code": "000001",
            "doc_type": "news",
            "title": "Test title",
            "summary": "Test summary",
            "content": "Test content",
            "source": "EastMoney",
            "source_url": "http://example.com/news/1",
            "publish_date": "2024-01-02 10:00:00",
        }
        item = await collector.transform(raw)
        assert item["title"] == "Test title"
        assert item["publish_date"] == datetime.datetime(2024, 1, 2, 10, 0, 0)
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_empty_title(self) -> None:
        collector = SinaNewsCollector({"source": "sina", "data_type": "news"})
        item = {
            "stock_code": "000001",
            "title": "",
            "source_url": "http://example.com/news/1",
            "publish_date": datetime.datetime(2024, 1, 2, 10, 0, 0),
        }
        assert await collector.validate(item) is False
