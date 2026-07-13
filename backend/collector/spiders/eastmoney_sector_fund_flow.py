"""EastMoney sector fund flow collector via akshare."""

import re
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep
from collector.settings import settings


class EastMoneySectorFundFlowCollector(BaseCollector):
    """东方财富板块资金流向采集器，写入 sector_fund_flow。"""

    SECTOR_TYPE_MAP: dict[str, str] = {
        "industry": "行业资金流",
        "concept": "概念资金流",
        "region": "地域资金流",
    }

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.sector_type = config.get("sector_type", "industry")
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                DeduplicateStep(key_fields=["sector_code", "sector_type", "trade_date"]),
                ValidateStep(required_fields=["sector_code", "sector_name", "trade_date"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(
        self, sector_type: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        sector_type = sector_type or self.sector_type
        indicator = "今日"
        ak_sector_type = self.SECTOR_TYPE_MAP.get(sector_type, "行业资金流")

        df = ak.stock_sector_fund_flow_rank(
            indicator=indicator, sector_type=ak_sector_type
        )
        trade_date = date.today()
        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            raw.append(
                {
                    "sector_code": _str(_find_col(row, ["板块代码"])),
                    "sector_name": _str(_find_col(row, ["板块名称"])),
                    "sector_type": sector_type,
                    "trade_date": trade_date,
                    "main_net_inflow": _parse_amount(_find_col(row, ["主力净流入-净额"])),
                    "super_large_net": _parse_amount(_find_col(row, ["超大单净流入-净额"])),
                    "large_net": _parse_amount(_find_col(row, ["大单净流入-净额"])),
                    "medium_net": _parse_amount(_find_col(row, ["中单净流入-净额"])),
                    "small_net": _parse_amount(_find_col(row, ["小单净流入-净额"])),
                    "top_stock_code": _str(_find_col(row, ["主力净流入最大股代码"])),
                    "top_stock_name": _str(_find_col(row, ["主力净流入最大股"])),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "sector_code": str(raw["sector_code"]),
            "sector_name": raw.get("sector_name"),
            "sector_type": raw.get("sector_type"),
            "trade_date": raw["trade_date"],
            "main_net_inflow": raw.get("main_net_inflow"),
            "super_large_net": raw.get("super_large_net"),
            "large_net": raw.get("large_net"),
            "medium_net": raw.get("medium_net"),
            "small_net": raw.get("small_net"),
            "top_stock_code": raw.get("top_stock_code"),
            "top_stock_name": raw.get("top_stock_name"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("sector_code") and item.get("sector_name") and item.get("trade_date")
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
                "sector_fund_flow",
                cleaned,
                conflict_key="sector_code, sector_type, trade_date",
            )
        await self._engine.dispose()
        return count


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


def _parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*([万亿万])?$", text)
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
