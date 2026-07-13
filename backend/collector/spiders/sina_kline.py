"""Sina K-line collector via akshare."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, ValidateStep
from collector.settings import settings


class SinaKlineCollector(BaseCollector):
    """新浪财经日 K / 分钟 K 数据采集器。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.period = config.get("period", "daily")
        self.pipeline = DataPipeline(
            steps=[
                DeduplicateStep(key_fields=["stock_code", "trade_date"]),
                ValidateStep(required_fields=["stock_code", "trade_date", "close"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(self, symbols: list[str] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            sina_symbol = self._to_sina_symbol(symbol)
            if self.period == "minute":
                df = ak.stock_zh_a_minute(symbol=sina_symbol, period="1")
                date_col = "day"
            else:
                df = ak.stock_zh_a_daily(symbol=sina_symbol)
                date_col = "date"

            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": symbol,
                        "trade_date": row[date_col],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "amount": row.get("amount"),
                        "amplitude": None,
                        "pct_change": None,
                        "turnover_rate": row.get("turnover"),
                    }
                )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "trade_date": raw["trade_date"],
            "open": float(raw["open"]) if raw.get("open") is not None else None,
            "high": float(raw["high"]) if raw.get("high") is not None else None,
            "low": float(raw["low"]) if raw.get("low") is not None else None,
            "close": float(raw["close"]) if raw.get("close") is not None else None,
            "volume": int(raw["volume"]) if raw.get("volume") is not None else None,
            "amount": float(raw["amount"]) if raw.get("amount") is not None else None,
            "amplitude": (
                float(raw["amplitude"]) if raw.get("amplitude") is not None else None
            ),
            "pct_change": (
                float(raw["pct_change"]) if raw.get("pct_change") is not None else None
            ),
            "turnover_rate": (
                float(raw["turnover_rate"])
                if raw.get("turnover_rate") is not None
                else None
            ),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        close = item.get("close")
        return (
            item.get("stock_code") is not None
            and item.get("trade_date") is not None
            and close is not None
            and close > 0
        )

    async def store(self, items: list[dict[str, Any]]) -> int:
        cleaned = await self.pipeline.process(items)
        if not cleaned:
            return 0

        table = "kline_minute" if self.period == "minute" else "kline_daily"
        session_maker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_maker() as session:
            exporter = PostgresExporter(session)
            count = await exporter.insert_many(
                table,
                cleaned,
                conflict_key="stock_code, trade_date",
            )
        await self._engine.dispose()
        return count

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        """将 6 位股票代码转换为 Sina 格式（sh/sz）。"""
        code = symbol.lstrip("sh").lstrip("sz").lstrip("bj")
        prefix = "sh" if code.startswith("6") else "sz"
        return f"{prefix}{code}"
