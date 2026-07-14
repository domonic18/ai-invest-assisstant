"""CNINFO periodic financial report collector via akshare."""

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep
from collector.settings import settings

DEFAULT_REPORT_TYPES = ["年报", "半年报", "一季报", "三季报"]


class CninfoFinancialReportCollector(BaseCollector):
    """巨潮资讯个股定期财报采集器，写入 news_announcement(doc_type='financial_report')。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.report_types = config.get("report_types") or DEFAULT_REPORT_TYPES
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                DeduplicateStep(key_fields=["source_url"]),
                ValidateStep(required_fields=["stock_code", "title", "publish_date"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        if end_date is None:
            end = date.today()
        else:
            end = _parse_date(end_date) or date.today()
        if start_date is None:
            start = end - timedelta(days=365)
        else:
            start = _parse_date(start_date) or (end - timedelta(days=365))

        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        symbols = symbols or ["000001"]
        report_types = self.report_types or DEFAULT_REPORT_TYPES
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            code = _clean_code(symbol)
            for category in report_types:
                try:
                    df = ak.stock_zh_a_disclosure_report_cninfo(
                        symbol=code,
                        category=category,
                        start_date=start_str,
                        end_date=end_str,
                    )
                except Exception:  # noqa: BLE001
                    continue
                if df.empty:
                    continue
                for _, row in df.iterrows():
                    url = _str(row.get("公告链接"))
                    raw.append(
                        {
                            "stock_code": _str(row.get("代码")) or code,
                            "doc_type": "financial_report",
                            "title": _str(row.get("公告标题")),
                            "summary": None,
                            "content": None,
                            "source": "cninfo",
                            "source_url": url,
                            "publish_date": _parse_datetime(_str(row.get("公告时间"))),
                            "sentiment": None,
                            "keywords": None,
                            "industry_tags": None,
                            "es_id": None,
                            "extra": json.dumps(_build_extra(url, category)),
                        }
                    )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "doc_type": "financial_report",
            "title": raw.get("title"),
            "summary": raw.get("summary"),
            "content": raw.get("content"),
            "source": raw.get("source"),
            "source_url": raw.get("source_url"),
            "publish_date": raw.get("publish_date"),
            "sentiment": raw.get("sentiment"),
            "keywords": raw.get("keywords"),
            "industry_tags": raw.get("industry_tags"),
            "es_id": raw.get("es_id"),
            "extra": raw.get("extra"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("stock_code")
            and item.get("title")
            and item.get("publish_date")
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


def _clean_code(symbol: str) -> str:
    return symbol.lstrip("sh").lstrip("sz").lstrip("bj").strip()


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _build_extra(url: str | None, category: str) -> dict[str, Any]:
    extra: dict[str, Any] = {"category": category}
    if url:
        extra["pdf_url"] = url
    return extra
