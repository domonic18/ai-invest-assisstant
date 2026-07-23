"""EastMoney research report collector via akshare."""

import json
import re
from datetime import datetime
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import clean_stock_code, to_float, to_optional_str


class EastMoneyResearchReportCollector(PostgresCollector):
    """东方财富个股研报采集器，写入 news_announcement(doc_type='research')。"""

    table = "news_announcement"
    conflict_key = "source_url"
    key_fields: ClassVar[list[str]] = ["source_url", "stock_code", "publish_date"]
    required_fields: ClassVar[list[str]] = ["stock_code", "title", "publish_date"]

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        for symbol in symbols:
            code = clean_stock_code(symbol)
            try:
                df = ak.stock_research_report_em(symbol=code)
            except Exception:  # noqa: BLE001
                continue
            if df.empty:
                continue
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": to_optional_str(row.get("股票代码")) or code,
                        "doc_type": "research",
                        "title": to_optional_str(row.get("报告名称")),
                        "summary": None,
                        "content": None,
                        "source": "eastmoney",
                        "source_url": None,
                        "publish_date": _parse_date(to_optional_str(row.get("日期"))),
                        "sentiment": None,
                        "keywords": None,
                        "industry_tags": _to_list(to_optional_str(row.get("行业"))),
                        "elasticsearch_doc_id": None,
                        "extra": json.dumps(_build_extra(row)),
                    }
                )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "doc_type": "research",
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
            item.get("stock_code") and item.get("title") and item.get("publish_date")
        )


def _to_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [value]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _build_extra(row: Any) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "broker": to_optional_str(row.get("机构")),
        "rating": to_optional_str(row.get("东财评级")),
    }
    eps_col = _find_forecast_col(row, "盈利预测-收益")
    pe_col = _find_forecast_col(row, "盈利预测-市盈率")
    if eps_col:
        extra["eps_forecast"] = to_float(row.get(eps_col))
    if pe_col:
        extra["pe_forecast"] = to_float(row.get(pe_col))
    return extra


def _find_forecast_col(row: Any, suffix: str) -> str | None:
    cols = list(row.index)
    for col in cols:
        col_str = str(col)
        if suffix in col_str:
            return col_str
    return None


def _extract_year(col: str) -> str | None:
    match = re.search(r"(\d{4})", col)
    return match.group(1) if match else None
