"""EastMoney dragon list (lhb) collector via akshare."""

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep
from collector.settings import settings


class EastMoneyDragonListCollector(BaseCollector):
    """东方财富龙虎榜采集器，写入 dragon_list。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                DeduplicateStep(key_fields=["trade_date", "stock_code", "rank_reason"]),
                ValidateStep(required_fields=["trade_date", "stock_code"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        end = _parse_date(end_date) or date.today()
        start = _parse_date(start_date) or end
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        df = ak.stock_lhb_detail_em(start_date=start_str, end_date=end_str)
        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            reason = _str(_find_col(row, ["解读", "上榜原因", "异动原因"]))
            if reason and len(reason) > 500:
                reason = reason[:500]
            raw.append(
                {
                    "trade_date": _parse_trade_date(_find_col(row, ["上榜日", "交易日期"])),
                    "stock_code": _str(_find_col(row, ["代码", "股票代码"])),
                    "stock_name": _str(_find_col(row, ["名称", "股票简称"])),
                    "rank_reason": reason,
                    "close_price": _to_float(_find_col(row, ["收盘价"])),
                    "change_pct": _to_float(_find_col(row, ["涨跌幅"])),
                    "net_buy_amount": _parse_amount(_find_col(row, ["龙虎榜净买额", "净买额"])),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "trade_date": raw["trade_date"],
            "stock_code": str(raw["stock_code"]),
            "stock_name": raw.get("stock_name"),
            "rank_reason": raw.get("rank_reason"),
            "close_price": raw.get("close_price"),
            "change_pct": raw.get("change_pct"),
            "net_buy_amount": raw.get("net_buy_amount"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(item.get("trade_date") and item.get("stock_code"))

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
                "dragon_list",
                cleaned,
                conflict_key="trade_date, stock_code, rank_reason",
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


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_trade_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
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
