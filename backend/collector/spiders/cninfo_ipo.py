"""CNINFO IPO information collector via akshare."""

from datetime import date, datetime
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import to_float, to_optional_str


class CninfoIpoCollector(PostgresCollector):
    """巨潮资讯新股发行信息采集器，写入 ipo_info。"""

    table = "ipo_info"
    conflict_key = "stock_code, subscription_date"
    key_fields: ClassVar[list[str]] = ["stock_code", "subscription_date"]
    required_fields: ClassVar[list[str]] = ["stock_code", "subscription_date"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        try:
            df = ak.stock_new_ipo_cninfo()
        except Exception:  # noqa: BLE001
            return []

        if df.empty:
            return []

        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            raw.append(
                {
                    "stock_code": to_optional_str(row.get("证劵代码")),
                    "stock_name": to_optional_str(row.get("证券简称")),
                    "listing_date": _to_date(row.get("上市日期")),
                    "subscription_date": _to_date(row.get("申购日期")),
                    "issue_price": to_float(row.get("发行价")),
                    "total_issue_quantity": to_float(row.get("总发行数量")),
                    "issue_pe_ratio": to_float(row.get("发行市盈率")),
                    "online_winning_rate": to_float(row.get("上网发行中签率")),
                    "lottery_result_date": _to_date(row.get("摇号结果公告日")),
                    "winning_announcement_date": _to_date(row.get("中签公告日")),
                    "payment_date": _to_date(row.get("中签缴款日")),
                    "online_subscription_limit": to_float(row.get("网上申购上限")),
                    "online_issue_quantity": to_float(row.get("上网发行数量")),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "stock_name": raw.get("stock_name"),
            "listing_date": raw.get("listing_date"),
            "subscription_date": raw.get("subscription_date"),
            "issue_price": raw.get("issue_price"),
            "total_issue_quantity": raw.get("total_issue_quantity"),
            "issue_pe_ratio": raw.get("issue_pe_ratio"),
            "online_winning_rate": raw.get("online_winning_rate"),
            "lottery_result_date": raw.get("lottery_result_date"),
            "winning_announcement_date": raw.get("winning_announcement_date"),
            "payment_date": raw.get("payment_date"),
            "online_subscription_limit": raw.get("online_subscription_limit"),
            "online_issue_quantity": raw.get("online_issue_quantity"),
            "source": "cninfo",
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(item.get("stock_code") and item.get("subscription_date"))


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    # Handle pandas NaT / numpy NaT explicitly before isinstance checks.
    if _is_na(value):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text or text.lower() == "nat":
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _is_na(value: Any) -> bool:
    """Return True for pandas/numpy missing-value sentinels."""
    try:
        import pandas as pd

        if value is pd.NaT or (isinstance(value, float) and pd.isna(value)):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        import numpy as np

        if value is np.nan or (isinstance(value, float) and np.isnan(value)):
            return True
    except Exception:  # noqa: BLE001
        pass
    return False
