"""THS (10jqka) sector fund flow collector — 东财板块资金流的备用渠道。

同花顺行业资金流（data.10jqka.com.cn/funds/hyzjl）与东财口径不同：
无板块代码（以行业名代替）、无超/大/中/小单拆分（写 NULL）、仅支持行业
板块。通过 akshare.stock_fund_flow_industry 获取（hexin-v 签名由 akshare
内置处理）。写入与东财采集器相同的 sector_fund_flow 表。
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep
from collector.settings import settings
from collector.spiders.utils import parse_cn_amount, to_optional_str


class ThsSectorFundFlowCollector(BaseCollector):
    """同花顺行业资金流向采集器（备用渠道），写入 sector_fund_flow。"""

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
        sector_type = sector_type or self.sector_type
        if sector_type != "industry":
            raise ValueError(f"同花顺渠道仅支持行业板块资金流，不支持: {sector_type}")

        import akshare as ak  # type: ignore[import-untyped]

        df = ak.stock_fund_flow_industry(symbol="即时")
        trade_date = date.today()
        raw: list[dict[str, Any]] = []
        for row in df.to_dict(orient="records"):
            sector_name = to_optional_str(row.get("行业"))
            raw.append(
                {
                    "sector_code": sector_name,
                    "sector_name": sector_name,
                    "sector_type": "industry",
                    "trade_date": trade_date,
                    "change_pct": _parse_pct(row.get("行业-涨跌幅")),
                    "main_net_inflow": _parse_net_amount(row.get("净额")),
                    "super_large_net": None,
                    "large_net": None,
                    "medium_net": None,
                    "small_net": None,
                    "top_stock_code": None,
                    "top_stock_name": to_optional_str(row.get("领涨股")),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "sector_code": str(raw["sector_code"]),
            "sector_name": raw.get("sector_name"),
            "sector_type": raw.get("sector_type"),
            "trade_date": raw["trade_date"],
            "change_pct": raw.get("change_pct"),
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
                update_columns=[
                    "sector_name",
                    "change_pct",
                    "main_net_inflow",
                    "super_large_net",
                    "large_net",
                    "medium_net",
                    "small_net",
                    "top_stock_code",
                    "top_stock_name",
                ],
                update_skip_null=True,
            )
        await self._engine.dispose()
        return count


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and value != value  # noqa: PLR0124


def _parse_pct(value: Any) -> float | None:
    """同花顺涨跌幅：数值或带 % 的字符串。"""
    if value is None or _is_nan(value):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return parse_cn_amount(str(value).strip().rstrip("%"))


def _parse_net_amount(value: Any) -> float | None:
    """同花顺净额：数值单位为亿元（需换算为元），字符串可能带中文单位。"""
    if value is None or _is_nan(value):
        return None
    if isinstance(value, Decimal):
        return float(value) * 100_000_000
    if isinstance(value, (int, float)):
        return float(value) * 100_000_000
    return parse_cn_amount(value)
