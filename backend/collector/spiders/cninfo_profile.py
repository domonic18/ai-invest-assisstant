"""CNINFO company profile collector via akshare."""

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, NormalizeStep, ValidateStep
from collector.settings import settings


class CninfoProfileCollector(BaseCollector):
    """巨潮资讯公司概况采集器，回写 stock_basic。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                ValidateStep(required_fields=["stock_code", "market"]),
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
                df = ak.stock_profile_cninfo(symbol=code)
            except Exception:  # noqa: BLE001
                continue
            if df.empty:
                continue
            row = df.iloc[0]
            raw.append(
                {
                    "stock_code": code,
                    "market": _guess_market(code),
                    "stock_name": _get(row, "A股简称"),
                    "full_name": _get(row, "公司名称"),
                    "industry_l1": _get(row, "所属行业"),
                    "legal_person": _get(row, "法人代表"),
                    "website": _get(row, "官方网站"),
                    "registered_capital": _parse_amount(_get(row, "注册资金")),
                    "business_scope": _get(row, "经营范围"),
                    "listing_date": _parse_date(_get(row, "上市日期")),
                    "province": None,
                    "city": None,
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "market": str(raw["market"]),
            "stock_name": raw.get("stock_name"),
            "full_name": raw.get("full_name"),
            "industry_l1": raw.get("industry_l1"),
            "legal_person": raw.get("legal_person"),
            "website": raw.get("website"),
            "registered_capital": raw.get("registered_capital"),
            "business_scope": raw.get("business_scope"),
            "listing_date": raw.get("listing_date"),
            "province": raw.get("province"),
            "city": raw.get("city"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(item.get("stock_code") and item.get("market"))

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
                "stock_basic",
                cleaned,
                conflict_key="stock_code, market",
                update_columns=[
                    "stock_name",
                    "full_name",
                    "industry_l1",
                    "legal_person",
                    "website",
                    "registered_capital",
                    "business_scope",
                    "listing_date",
                    "province",
                    "city",
                ],
            )
        await self._engine.dispose()
        return count


def _clean_code(symbol: str) -> str:
    return symbol.lstrip("sh").lstrip("sz").lstrip("bj").strip()


def _guess_market(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    if code.startswith("8") or code.startswith("4"):
        return "bj"
    return "sz"


def _get(row: Any, col: str) -> Any:
    try:
        return row[col]
    except KeyError:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*([万亿万])?元?$", text)
    if not match:
        try:
            return float(text)
        except (TypeError, ValueError):
            return None
    number = float(match.group(1))
    unit = match.group(2)
    multiplier = {"万": 10_000, "亿": 100_000_000, "万亿": 1_000_000_000_000}.get(
        unit, 1
    )
    return number * multiplier
