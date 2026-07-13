"""Sina auction data collector via hq.sinajs.cn real-time depth."""

from datetime import date, datetime, time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, ValidateStep
from collector.settings import settings


class SinaAuctionCollector(BaseCollector):
    """新浪财经集合竞价数据采集器（基于实时买卖盘快照）。"""

    DEFAULT_BASE_URL = "https://hq.sinajs.cn"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.match_time = config.get("match_time", time(9, 25, 0))
        self.base_url = config.get("base_url") or self.DEFAULT_BASE_URL
        self.api_key = config.get("api_key")
        self.pipeline = DataPipeline(
            steps=[
                DeduplicateStep(key_fields=["stock_code", "trade_date", "match_time"]),
                ValidateStep(required_fields=["stock_code", "trade_date", "match_time"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(self, symbols: list[str] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        trade_date = date.today()

        for symbol in symbols:
            snapshot = await self._fetch_snapshot(symbol)
            snapshot["stock_code"] = symbol
            snapshot["trade_date"] = trade_date
            snapshot["match_time"] = self.match_time
            raw.append(snapshot)

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
            "price": _to_float(raw.get("current")),
            "volume": _to_int(raw.get("volume")),
            "bid_prices": [_to_float(raw.get(f"buy_{i}_price")) for i in range(1, 6)],
            "bid_volumes": [_to_int(raw.get(f"buy_{i}_vol")) for i in range(1, 6)],
            "ask_prices": [_to_float(raw.get(f"sell_{i}_price")) for i in range(1, 6)],
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

    async def _fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        """Fetch a Sina real-time snapshot and parse the 5-level depth."""
        sina_symbol = self._to_sina_symbol(symbol)
        url = f"{self.base_url.rstrip('/')}/list={sina_symbol}"
        headers = {"Referer": "https://finance.sina.com.cn"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
        response.encoding = "GB18030"
        text = response.text

        try:
            payload = text.split('"')[1]
        except IndexError as exc:
            raise ValueError(f"Unexpected Sina response for {symbol}: {text[:200]}") from exc

        parts = payload.split(",")
        # Sina returns a short 33-field snapshot outside trading hours and a
        # longer one during trading. We only need indices 0-5 and 8-29.
        if len(parts) < 30:
            raise ValueError(f"Incomplete Sina snapshot for {symbol}: {parts}")

        # Sina field order:
        # 0 name, 1 open, 2 prev_close, 3 current, 4 high, 5 low,
        # 6 bid1_price, 7 ask1_price, 8 volume, 9 amount,
        # 10 buy1_vol, 11 buy1_price, 12 buy2_vol, 13 buy2_price, ...
        def _part(idx: int) -> str | None:
            return parts[idx] if idx < len(parts) else None

        snapshot: dict[str, Any] = {
            "name": parts[0],
            "open": parts[1],
            "prev_close": parts[2],
            "current": parts[3],
            "high": parts[4],
            "low": parts[5],
            "volume": parts[8],
            "amount": parts[9],
        }
        for i in range(1, 6):
            snapshot[f"buy_{i}_vol"] = _part(10 + (i - 1) * 2)
            snapshot[f"buy_{i}_price"] = _part(11 + (i - 1) * 2)
            snapshot[f"sell_{i}_vol"] = _part(20 + (i - 1) * 2)
            snapshot[f"sell_{i}_price"] = _part(21 + (i - 1) * 2)

        return snapshot

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        """将 6 位股票代码转换为 Sina 格式（sh/sz）。"""
        code = symbol.lstrip("sh").lstrip("sz").lstrip("bj")
        prefix = "sh" if code.startswith("6") else "sz"
        return f"{prefix}{code}"
