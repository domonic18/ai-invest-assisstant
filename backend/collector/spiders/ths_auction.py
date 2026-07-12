"""TongHuaShun auction data collector via akshare bid/ask snapshot."""

from datetime import date, datetime, time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, ValidateStep
from collector.settings import settings


class ThsAuctionCollector(BaseCollector):
    """同花顺集合竞价数据采集器（基于实时买卖盘快照）。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.match_time = config.get("match_time", time(9, 25, 0))
        self.pipeline = DataPipeline(
            steps=[
                DeduplicateStep(key_fields=["stock_code", "trade_date", "match_time"]),
                ValidateStep(required_fields=["stock_code", "trade_date", "match_time"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(self, symbols: list[str] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        trade_date = date.today()

        for symbol in symbols:
            df = ak.stock_bid_ask_em(symbol=symbol)
            data = dict(zip(df["item"], df["value"]))
            data["stock_code"] = symbol
            data["trade_date"] = trade_date
            data["match_time"] = self.match_time
            raw.append(data)

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        def _to_float(value: Any) -> float | None:
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def _to_int(value: Any) -> int | None:
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        trade_date = raw["trade_date"]
        if isinstance(trade_date, str):
            trade_date = datetime.strptime(trade_date, "%Y-%m-%d").date()

        match_time = raw["match_time"]
        if isinstance(match_time, str):
            match_time = datetime.strptime(match_time, "%H:%M:%S").time()

        return {
            "stock_code": str(raw["stock_code"]),
            "trade_date": trade_date,
            "match_time": match_time,
            "price": _to_float(raw.get("最新")),
            "volume": _to_int(raw.get("总手")),
            "bid_prices": [_to_float(raw.get(f"buy_{i}")) for i in range(1, 6)],
            "bid_volumes": [_to_int(raw.get(f"buy_{i}_vol")) for i in range(1, 6)],
            "ask_prices": [_to_float(raw.get(f"sell_{i}")) for i in range(1, 6)],
            "ask_volumes": [_to_int(raw.get(f"sell_{i}_vol")) for i in range(1, 6)],
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return (
            item.get("stock_code") is not None
            and item.get("trade_date") is not None
            and item.get("match_time") is not None
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
                "auction_data",
                cleaned,
                conflict_key="stock_code, trade_date, match_time",
            )
        await self._engine.dispose()
        return count
