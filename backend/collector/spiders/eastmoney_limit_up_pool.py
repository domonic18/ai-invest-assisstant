"""EastMoney limit-up pool collector via akshare.

Fetches the daily 涨停股池 (stock_zt_pool_em) and stores it into
``limit_up_pool`` for the daily-review dashboard (涨停板 / 连板天梯).
"""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep
from collector.settings import settings

_UPDATE_COLUMNS = [
    "stock_name",
    "change_pct",
    "latest_price",
    "turnover_rate",
    "sealed_amount",
    "first_seal_time",
    "last_seal_time",
    "break_count",
    "limit_stat",
    "consecutive_boards",
    "industry",
    "source",
]


class EastMoneyLimitUpPoolCollector(BaseCollector):
    """东方财富涨停股池采集器，写入 limit_up_pool。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                DeduplicateStep(key_fields=["trade_date", "stock_code"]),
                ValidateStep(required_fields=["trade_date", "stock_code"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)

    async def collect(
        self, trade_date: date | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        target = trade_date or date.today()
        df = ak.stock_zt_pool_em(date=target.strftime("%Y%m%d"))
        if df.empty:
            return []

        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            raw.append(
                {
                    "trade_date": target,
                    "stock_code": _str(row.get("代码")),
                    "stock_name": _str(row.get("名称")),
                    "change_pct": _to_float(row.get("涨跌幅")),
                    "latest_price": _to_float(row.get("最新价")),
                    "turnover_rate": _to_float(row.get("换手率")),
                    "sealed_amount": _to_float(row.get("封板资金")),
                    "first_seal_time": _str(row.get("首次封板时间")),
                    "last_seal_time": _str(row.get("最后封板时间")),
                    "break_count": _to_int(row.get("炸板次数")),
                    "limit_stat": _str(row.get("涨停统计")),
                    "consecutive_boards": _to_int(row.get("连板数")),
                    "industry": _str(row.get("所属行业")),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "trade_date": raw["trade_date"],
            "stock_code": str(raw["stock_code"]),
            "stock_name": raw.get("stock_name"),
            "change_pct": raw.get("change_pct"),
            "latest_price": raw.get("latest_price"),
            "turnover_rate": raw.get("turnover_rate"),
            "sealed_amount": raw.get("sealed_amount"),
            "first_seal_time": raw.get("first_seal_time"),
            "last_seal_time": raw.get("last_seal_time"),
            "break_count": raw.get("break_count"),
            "limit_stat": raw.get("limit_stat"),
            "consecutive_boards": raw.get("consecutive_boards"),
            "industry": raw.get("industry"),
            "source": "eastmoney",
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
                "limit_up_pool",
                cleaned,
                conflict_key="trade_date, stock_code",
                update_columns=_UPDATE_COLUMNS,
                update_skip_null=True,
            )
        await self._engine.dispose()
        return count


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
        return None if result != result else result
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
