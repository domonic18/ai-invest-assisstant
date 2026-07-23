"""Sina finance news collector via akshare EastMoney stock news."""

from datetime import datetime
from typing import Any, ClassVar

from collector.core.base import PostgresCollector


class SinaNewsCollector(PostgresCollector):
    """新浪财经新闻数据采集器（基于东方财富个股新闻接口）。"""

    table = "news_announcement"
    conflict_key = "source_url"
    normalize = False
    key_fields: ClassVar[list[str]] = ["source_url"]
    required_fields: ClassVar[list[str]] = ["title", "source_url", "publish_date"]

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            df = ak.stock_news_em(symbol=symbol)
            if df is None or df.empty:
                continue
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
            "source": (
                str(raw.get("source", "")) if raw.get("source") is not None else None
            ),
            "source_url": str(raw["source_url"]),
            "publish_date": publish_date,
            "sentiment": None,
            "keywords": None,
            "industry_tags": None,
            "elasticsearch_doc_id": None,
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return (
            bool(item.get("title"))
            and bool(item.get("source_url"))
            and item.get("publish_date") is not None
        )
