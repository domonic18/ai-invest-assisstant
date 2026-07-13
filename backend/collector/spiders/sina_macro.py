"""Sina macro economic indicator collector via akshare."""

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep
from collector.settings import settings


class SinaMacroCollector(BaseCollector):
    """新浪财经宏观经济指标采集器，写入 macro_indicator。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                DeduplicateStep(key_fields=["indicator_name", "period_type", "publish_date"]),
                ValidateStep(required_fields=["indicator_name", "period_type", "publish_date"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(
        self, indicators: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        indicators = indicators or ["cpi", "pmi", "gdp"]
        raw: list[dict[str, Any]] = []
        for name in indicators:
            try:
                if name == "cpi":
                    df = ak.macro_china_cpi()
                    raw.extend(_parse_cpi(df))
                elif name == "pmi":
                    df = ak.macro_china_pmi()
                    raw.extend(_parse_pmi(df))
                elif name == "gdp":
                    df = ak.macro_china_gdp()
                    raw.extend(_parse_gdp(df))
            except Exception:  # noqa: BLE001
                continue
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "indicator_name": raw["indicator_name"],
            "period_type": raw["period_type"],
            "publish_date": raw["publish_date"],
            "value": raw.get("value"),
            "value_yoy": raw.get("value_yoy"),
            "value_mom": raw.get("value_mom"),
            "source": raw.get("source"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("indicator_name") and item.get("period_type") and item.get("publish_date")
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
                "macro_indicator",
                cleaned,
                conflict_key="indicator_name, period_type, publish_date",
            )
        await self._engine.dispose()
        return count


def _parse_cpi(df: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        period = _str(_find_col(row, ["月份", "月"]))
        publish_date = _parse_month_period(period)
        value = _to_float(_find_col(row, ["全国-当月", "当月", "全国"]))
        yoy = _to_float(_find_col(row, ["全国-同比增长", "同比增长"]))
        mom = _to_float(_find_col(row, ["全国-环比增长", "环比增长"]))
        rows.append(
            {
                "indicator_name": "cpi",
                "period_type": "month",
                "publish_date": publish_date,
                "value": value,
                "value_yoy": yoy,
                "value_mom": mom,
                "source": "sina",
            }
        )
    return rows


def _parse_pmi(df: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        period = _str(_find_col(row, ["月份", "月"]))
        publish_date = _parse_month_period(period)
        value = _to_float(_find_col(row, ["制造业-指数", "制造业采购经理指数", "指数"]))
        rows.append(
            {
                "indicator_name": "pmi",
                "period_type": "month",
                "publish_date": publish_date,
                "value": value,
                "value_yoy": None,
                "value_mom": None,
                "source": "sina",
            }
        )
    return rows


def _parse_gdp(df: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        period = _str(_find_col(row, ["季度"]))
        publish_date = _parse_quarter_period(period)
        value = _to_float(_find_col(row, ["国内生产总值-绝对值", "GDP-绝对值", "绝对值"]))
        yoy = _to_float(_find_col(row, ["国内生产总值-同比增长", "GDP-同比增长", "同比增长"]))
        rows.append(
            {
                "indicator_name": "gdp",
                "period_type": "quarter",
                "publish_date": publish_date,
                "value": value,
                "value_yoy": yoy,
                "value_mom": None,
                "source": "sina",
            }
        )
    return rows


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _find_col(row: Any, candidates: list[str]) -> Any:
    for col in candidates:
        try:
            return row[col]
        except KeyError:
            continue
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_month_period(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    # e.g. "2024年06月" / "2024年06月份"
    match = re.match(r"^(\d{4})[年/-](\d{1,2})月份?$", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)
    for fmt in ("%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_quarter_period(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    match = re.match(r"^(\d{4})年第?(\d)季度?$", text)
    if match:
        year = int(match.group(1))
        quarter = int(match.group(2))
        month = (quarter - 1) * 3 + 1
        return date(year, month, 1)
    return None
