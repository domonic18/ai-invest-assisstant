"""Sina finance news collector via akshare EastMoney stock news."""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, ValidateStep
from collector.settings import settings


class SinaNewsCollector(BaseCollector):
    """新浪财经新闻数据采集器（基于东方财富个股新闻接口）。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.pipeline = DataPipeline(
            steps=[
                DeduplicateStep(key_fields=["source_url"]),
                ValidateStep(required_fields=["title", "source_url", "publish_date"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(self, symbols: list[str] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            df = ak.stock_news_em(symbol=symbol)
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": symbol,
                        "doc_type": "news",
                        "title": row["新闻标题"],
                        "summary": row["新闻内容"],
                        "content": row["新闻内容"],
                        "source": row["文章来源"],
                        "source_url": row["新闻链接"],
                        "publish_date": row["发布时间"],
                    }
                )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        publish_date = raw["publish_date"]
        if isinstance(publish_date, str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    publish_date = datetime.strptime(publish_date, fmt)
                    break
                except ValueError:
                    continue

        return {
            "stock_code": str(raw["stock_code"]),
            "doc_type": str(raw.get("doc_type", "news")),
            "title": str(raw["title"]),
            "summary": str(raw.get("summary", "")),
            "content": str(raw.get("content", "")),
            "source": str(raw.get("source", "")) if raw.get("source") is not None else None,
            "source_url": str(raw["source_url"]),
            "publish_date": publish_date,
            "sentiment": None,
            "keywords": None,
            "industry_tags": None,
            "es_id": None,
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return (
            bool(item.get("title"))
            and bool(item.get("source_url"))
            and item.get("publish_date") is not None
        )

    async def store(self, items: list[dict[str, Any]]) -> int:
        cleaned = await self.pipeline.process(items)
        if not cleaned:
            return 0

        session_maker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_maker() as session:
            exporter = PostgresExporter(session)
            count = await exporter.insert_many(
                "news_announcement",
                cleaned,
                conflict_key="source_url",
            )
        await self._engine.dispose()
        return count
