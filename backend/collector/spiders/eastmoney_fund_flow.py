"""EastMoney individual stock fund flow collector via akshare."""

import re
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, ValidateStep
from collector.settings import settings


class EastMoneyFundFlowCollector(BaseCollector):
    """东方财富个股资金流向数据采集器（最新交易日全市场快照）。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")
        self.pipeline = DataPipeline(
            steps=[
                DeduplicateStep(key_fields=["stock_code", "trade_date"]),
                ValidateStep(required_fields=["stock_code", "trade_date"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(
        self, symbols: list[str | dict[str, str]] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        df = ak.stock_fund_flow_individual()
        trade_date = date.today()
        raw: list[dict[str, Any]] = []

        # Normalize requested symbols to plain 6-digit codes.
        requested: set[str] | None = None
        if symbols:
            requested = set()
            for symbol in symbols:
                if isinstance(symbol, str):
                    requested.add(symbol.lstrip("sh").lstrip("sz").lstrip("bj"))
                else:
                    requested.add(symbol["stock"].lstrip("sh").lstrip("sz").lstrip("bj"))

        for _, row in df.iterrows():
            stock_code = str(row["股票代码"]).zfill(6)
            if requested and stock_code not in requested:
                continue
            raw.append(
                {
                    "stock_code": stock_code,
                    "trade_date": trade_date,
                    "main_net_inflow": row["净额"],
                    "super_large_net": None,
                    "large_net": None,
                    "medium_net": None,
                    "small_net": None,
                }
            )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "trade_date": raw["trade_date"],
            "main_net_inflow": _parse_chinese_amount(raw.get("main_net_inflow")),
            "super_large_net": _to_float(raw.get("super_large_net")),
            "large_net": _to_float(raw.get("large_net")),
            "medium_net": _to_float(raw.get("medium_net")),
            "small_net": _to_float(raw.get("small_net")),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return (
            item.get("stock_code") is not None
            and item.get("trade_date") is not None
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
                "fund_flow",
                cleaned,
                conflict_key="stock_code, trade_date",
            )
        await self._engine.dispose()
        return count


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_chinese_amount(value: Any) -> float | None:
    """Parse strings like ``1.23亿``, ``-456.78万`` into yuan."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*([万亿])?$", text)
    if not match:
        return _to_float(value)
    number = float(match.group(1))
    unit = match.group(2)
    multiplier = {"万": 10_000, "亿": 100_000_000}.get(unit, 1)
    return number * multiplier
