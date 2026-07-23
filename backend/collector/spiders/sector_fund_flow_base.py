"""板块资金流向采集器共享基类 — eastmoney/ths 等渠道共用表配置与清洗逻辑。

子类只需实现 collect（产出 sector_code/sector_name/trade_date/change_pct/
main_net_inflow/... 键的原始字典），不支持的字段填 None。
"""

from typing import Any, ClassVar

from collector.core.base import PostgresCollector

_UPDATE_COLUMNS = [
    "sector_name",
    "change_pct",
    "main_net_inflow",
    "super_large_net",
    "large_net",
    "medium_net",
    "small_net",
    "top_stock_code",
    "top_stock_name",
]


class BaseSectorFundFlowCollector(PostgresCollector):
    """板块资金流向采集器基类，写入 capital_fund_flow_sector。"""

    table = "capital_fund_flow_sector"
    conflict_key = "sector_code, sector_type, trade_date"
    update_skip_null = True
    update_columns: ClassVar[list[str]] = _UPDATE_COLUMNS
    key_fields: ClassVar[list[str]] = ["sector_code", "sector_type", "trade_date"]
    required_fields: ClassVar[list[str]] = ["sector_code", "sector_name", "trade_date"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.sector_type = config.get("sector_type", "industry")

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
            item.get("sector_code")
            and item.get("sector_name")
            and item.get("trade_date")
        )
