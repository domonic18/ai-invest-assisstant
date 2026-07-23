"""CNINFO disclosure/announcement collector via akshare."""

import json
from datetime import date, datetime, timedelta
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

from collector.core.base import PostgresCollector
from collector.core.parsing import clean_stock_code, parse_date, to_optional_str


class CninfoDisclosureCollector(PostgresCollector):
    """巨潮资讯公告采集器，写入 news_announcement(doc_type='announcement')。"""

    table = "news_announcement"
    conflict_key = "source_url"
    key_fields: ClassVar[list[str]] = ["source_url"]
    required_fields: ClassVar[list[str]] = ["stock_code", "title", "publish_date"]

    async def collect(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        end = parse_date(end_date) or date.today()
        start = parse_date(start_date) or (end - timedelta(days=7))

        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        for symbol in symbols:
            code = clean_stock_code(symbol)
            try:
                df = ak.stock_zh_a_disclosure_report_cninfo(
                    symbol=code,
                    start_date=start_str,
                    end_date=end_str,
                )
            except Exception:  # noqa: BLE001
                continue
            if df.empty:
                continue
            for _, row in df.iterrows():
                url = to_optional_str(row.get("公告链接"))
                raw.append(
                    {
                        "stock_code": to_optional_str(row.get("代码")) or code,
                        "doc_type": "announcement",
                        "title": to_optional_str(row.get("公告标题")),
                        "summary": None,
                        "content": None,
                        "source": "cninfo",
                        "source_url": url,
                        "publish_date": _parse_datetime(
                            to_optional_str(row.get("公告时间"))
                        ),
                        "sentiment": None,
                        "keywords": None,
                        "industry_tags": None,
                        "elasticsearch_doc_id": None,
                        "extra": json.dumps(_build_extra(url)),
                    }
                )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "doc_type": "announcement",
            "title": raw.get("title"),
            "summary": raw.get("summary"),
            "content": raw.get("content"),
            "source": raw.get("source"),
            "source_url": raw.get("source_url"),
            "publish_date": raw.get("publish_date"),
            "sentiment": raw.get("sentiment"),
            "keywords": raw.get("keywords"),
            "industry_tags": raw.get("industry_tags"),
            "elasticsearch_doc_id": raw.get("elasticsearch_doc_id"),
            "extra": raw.get("extra"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("stock_code")
            and item.get("title")
            and item.get("publish_date")
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _build_extra(url: str | None) -> dict[str, Any]:
    if not url:
        return {}
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        return {
            "announcement_id": qs.get("announcementId", [None])[0],
            "org_id": qs.get("orgId", [None])[0],
            "pdf_url": url,
        }
    except Exception:  # noqa: BLE001
        return {"pdf_url": url}
