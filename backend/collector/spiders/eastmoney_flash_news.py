"""东方财富全球快讯采集器（akshare ``stock_info_global_em``）。

市场级 7×24 快讯，无标的维度，写入 ``news_document``（doc_type=news，
source=eastmoney），``source_url`` 唯一键幂等 upsert（DO NOTHING）。
"""

from datetime import datetime, timezone
from typing import Any, ClassVar

from app.core.clock import CN_TZ
from collector.core.base import PostgresCollector
from collector.core.parsing import to_optional_str

_PUBLISH_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def _parse_publish_time(raw: Any) -> datetime | None:
    """解析东财快讯「发布时间」（北京时间）为 aware UTC。"""
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc)
    text = to_optional_str(raw)
    if text is None:
        return None
    for fmt in _PUBLISH_TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=CN_TZ).astimezone(
                timezone.utc
            )
        except ValueError:
            continue
    return None


class EastmoneyFlashNewsCollector(PostgresCollector):
    """东方财富全球快讯采集器，写入 news_document（source_url 幂等）。"""

    table = "news_document"
    conflict_key = "source_url"
    normalize = False
    key_fields: ClassVar[list[str]] = ["source_url"]
    required_fields: ClassVar[list[str]] = ["title", "source_url", "publish_date"]

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        del symbols  # 市场级快讯，无标的维度
        df = ak.stock_info_global_em()
        if df is None or df.empty:
            return []

        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            source_url = to_optional_str(row.get("链接"))
            if source_url is None:
                continue
            raw.append(
                {
                    "标题": row.get("标题"),
                    "摘要": row.get("摘要"),
                    "链接": source_url,
                    "发布时间": row.get("发布时间"),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        summary = to_optional_str(raw.get("摘要")) or ""
        return {
            "doc_type": "news",
            "title": to_optional_str(raw.get("标题")) or "",
            "summary": summary,
            "content": summary,
            "source": "eastmoney",
            "source_url": to_optional_str(raw.get("链接")),
            "publish_date": _parse_publish_time(raw.get("发布时间")),
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
