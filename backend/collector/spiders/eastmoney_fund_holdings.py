"""EastMoney fund holdings collector via akshare."""

from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep
from collector.settings import settings

DEFAULT_REPORT_DATE = "20250331"


class EastMoneyFundHoldingsCollector(BaseCollector):
    """东方财富个股基金持仓采集器，写入 fund_holdings。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.report_date = config.get("report_date") or DEFAULT_REPORT_DATE
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                DeduplicateStep(key_fields=["stock_code", "report_date"]),
                ValidateStep(required_fields=["stock_code", "report_date"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        try:
            df = ak.stock_report_fund_hold(
                symbol="基金持仓",
                date=self.report_date,
            )
        except Exception:  # noqa: BLE001
            return []

        if df.empty:
            return []

        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            raw.append(
                {
                    "stock_code": _str(row.get("股票代码")),
                    "stock_name": _str(row.get("股票简称")),
                    "report_date": _parse_report_date(self.report_date),
                    "holding_fund_count": _to_int(row.get("持有基金家数")),
                    "total_holding_quantity": _to_int(row.get("持股总数")),
                    "holding_market_value": _to_float(row.get("持股市值")),
                    "holding_change": _str(row.get("持股变化")),
                    "holding_change_quantity": _to_int(row.get("持股变动数值")),
                    "holding_change_ratio": _to_float(row.get("持股变动比例")),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "stock_name": raw.get("stock_name"),
            "report_date": raw.get("report_date"),
            "holding_fund_count": raw.get("holding_fund_count"),
            "total_holding_quantity": raw.get("total_holding_quantity"),
            "holding_market_value": raw.get("holding_market_value"),
            "holding_change": raw.get("holding_change"),
            "holding_change_quantity": raw.get("holding_change_quantity"),
            "holding_change_ratio": raw.get("holding_change_ratio"),
            "source": "eastmoney",
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(item.get("stock_code") and item.get("report_date"))

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
                "fund_holdings",
                cleaned,
                conflict_key="stock_code, report_date",
            )
        await self._engine.dispose()
        return count


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number  # NaN check


def _parse_report_date(value: str) -> date | None:
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None
