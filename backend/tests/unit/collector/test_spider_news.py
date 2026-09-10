"""东财全球快讯 spider 契约测试。"""


import datetime

import pytest

from collector.spiders.eastmoney_flash_news import EastmoneyFlashNewsCollector


@pytest.mark.unit
class TestEastmoneyFlashNewsCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = EastmoneyFlashNewsCollector(
            {"source": "eastmoney", "data_type": "news"}
        )
        raw = {
            "标题": "Test title",
            "摘要": "Test summary",
            "链接": "http://example.com/news/1",
            "发布时间": "2024-01-02 10:00:00",
        }
        item = await collector.transform(raw)
        assert item["doc_type"] == "news"
        assert item["source"] == "eastmoney"
        assert item["title"] == "Test title"
        assert item["summary"] == "Test summary"
        assert item["content"] == "Test summary"
        assert item["source_url"] == "http://example.com/news/1"
        # 北京时间 10:00 -> aware UTC 02:00
        assert item["publish_date"] == datetime.datetime(
            2024, 1, 2, 2, 0, 0, tzinfo=datetime.timezone.utc
        )
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_empty_title(self) -> None:
        collector = EastmoneyFlashNewsCollector(
            {"source": "eastmoney", "data_type": "news"}
        )
        item = {
            "title": "",
            "source_url": "http://example.com/news/1",
            "publish_date": datetime.datetime(
                2024, 1, 2, 2, 0, 0, tzinfo=datetime.timezone.utc
            ),
        }
        assert await collector.validate(item) is False
