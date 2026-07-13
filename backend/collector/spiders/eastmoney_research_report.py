"""EastMoney research report collector via akshare."""

import json
import math
import re
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep
from collector.settings import settings


class EastMoneyResearchReportCollector(BaseCollector):
    """东方财富个股研报采集器，写入 news_announcement(doc_type='research')。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                DeduplicateStep(key_fields=["source_url", "stock_code", "publish_date"]),
                ValidateStep(required_fields=["stock_code", "title", "publish_date"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        for symbol in symbols:
            code = _clean_code(symbol)
            try:
                df = ak.stock_research_report_em(symbol=code)
            except Exception:  # noqa: BLE001
                continue
            if df.empty:
                continue
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": _str(row.get("股票代码")) or code,
                        "doc_type": "research",
                        "title": _str(row.get("报告名称")),
                        "summary": None,
                        "content": None,
                        "source": "eastmoney",
                        "source_url": None,
                        "publish_date": _parse_date(_str(row.get("日期"))),
                        "sentiment": None,
                        "keywords": None,
                        "industry_tags": _to_list(_str(row.get("行业"))),
                        "es_id": None,
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
            "es_id": raw.get("es_id"),
            "extra": raw.get("extra"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("stock_code") and item.get("title") and item.get("publish_date")
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
        "broker": _str(row.get("机构")),
        "rating": _str(row.get("东财评级")),
    }
    eps_col = _find_forecast_col(row, "盈利预测-收益")
    pe_col = _find_forecast_col(row, "盈利预测-市盈率")
    if eps_col:
        extra["eps_forecast"] = _to_float(row.get(eps_col))
    if pe_col:
        extra["pe_forecast"] = _to_float(row.get(pe_col))
    return extra


def _find_forecast_col(row: Any, suffix: str) -> str | None:
    cols = list(row.index)
    for col in cols:
        col_str = str(col)
        if suffix in col_str:
            return col_str
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _extract_year(col: str) -> str | None:
    match = re.search(r"(\d{4})", col)
    return match.group(1) if match else None
