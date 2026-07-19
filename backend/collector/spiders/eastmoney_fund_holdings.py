"""EastMoney fund holdings collector via akshare."""

from datetime import date, datetime
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import to_float, to_int, to_optional_str

DEFAULT_REPORT_DATE = "20250331"


class EastMoneyFundHoldingsCollector(PostgresCollector):
    """东方财富个股基金持仓采集器，写入 fund_holdings。"""

    table = "fund_holdings"
    conflict_key = "stock_code, report_date"
    key_fields: ClassVar[list[str]] = ["stock_code", "report_date"]
    required_fields: ClassVar[list[str]] = ["stock_code", "report_date"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.report_date = config.get("report_date") or DEFAULT_REPORT_DATE
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")

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
                    "stock_code": to_optional_str(row.get("股票代码")),
                    "stock_name": to_optional_str(row.get("股票简称")),
                    "report_date": _parse_report_date(self.report_date),
                    "holding_fund_count": to_int(row.get("持有基金家数")),
                    "total_holding_quantity": to_int(row.get("持股总数")),
                    "holding_market_value": to_float(row.get("持股市值")),
                    "holding_change": to_optional_str(row.get("持股变化")),
                    "holding_change_quantity": to_int(row.get("持股变动数值")),
                    "holding_change_ratio": to_float(row.get("持股变动比例")),
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


def _parse_report_date(value: str) -> date | None:
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None
