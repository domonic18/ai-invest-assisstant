"""EastMoney individual stock fund flow collector via akshare."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, ValidateStep
from collector.settings import settings


class EastMoneyFundFlowCollector(BaseCollector):
    """东方财富个股资金流向数据采集器。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
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

        symbols = symbols or [{"stock": "000001", "market": "sz"}]
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            if isinstance(symbol, str):
                stock = symbol
                market = "sh" if stock.startswith("6") else "sz"
            else:
                stock = symbol["stock"]
                market = symbol.get("market", "sh" if stock.startswith("6") else "sz")

            df = ak.stock_individual_fund_flow(stock=stock, market=market)
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": stock,
                        "trade_date": row["日期"],
                        "main_net_inflow": row["主力净流入-净额"],
                        "super_large_net": row["超大单净流入-净额"],
                        "large_net": row["大单净流入-净额"],
                        "medium_net": row["中单净流入-净额"],
                        "small_net": row["小单净流入-净额"],
                    }
                )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        def _to_float(value: Any) -> float | None:
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        return {
            "stock_code": str(raw["stock_code"]),
            "trade_date": raw["trade_date"],
            "main_net_inflow": _to_float(raw.get("main_net_inflow")),
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
