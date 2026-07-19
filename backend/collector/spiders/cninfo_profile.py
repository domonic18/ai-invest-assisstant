"""CNINFO company profile collector via akshare."""

from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import clean_stock_code, parse_cn_amount, parse_date

_UPDATE_COLUMNS = [
    "stock_name",
    "full_name",
    "industry_l1",
    "legal_person",
    "website",
    "registered_capital",
    "business_scope",
    "listing_date",
    "province",
    "city",
]


class CninfoProfileCollector(PostgresCollector):
    """巨潮资讯公司概况采集器，回写 stock_basic。"""

    table = "stock_basic"
    conflict_key = "stock_code, market"
    update_columns: ClassVar[list[str]] = _UPDATE_COLUMNS
    required_fields: ClassVar[list[str]] = ["stock_code", "market"]

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []
        for symbol in symbols:
            code = clean_stock_code(symbol)
            try:
                df = ak.stock_profile_cninfo(symbol=code)
            except Exception:  # noqa: BLE001
                continue
            if df.empty:
                continue
            row = df.iloc[0]
            raw.append(
                {
                    "stock_code": code,
                    "market": _guess_market(code),
                    "stock_name": _get(row, "A股简称"),
                    "full_name": _get(row, "公司名称"),
                    "industry_l1": _get(row, "所属行业"),
                    "legal_person": _get(row, "法人代表"),
                    "website": _get(row, "官方网站"),
                    "registered_capital": parse_cn_amount(_get(row, "注册资金")),
                    "business_scope": _get(row, "经营范围"),
                    "listing_date": parse_date(_get(row, "上市日期")),
                    "province": None,
                    "city": None,
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "market": str(raw["market"]),
            "stock_name": raw.get("stock_name"),
            "full_name": raw.get("full_name"),
            "industry_l1": raw.get("industry_l1"),
            "legal_person": raw.get("legal_person"),
            "website": raw.get("website"),
            "registered_capital": raw.get("registered_capital"),
            "business_scope": raw.get("business_scope"),
            "listing_date": raw.get("listing_date"),
            "province": raw.get("province"),
            "city": raw.get("city"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(item.get("stock_code") and item.get("market"))


def _guess_market(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    if code.startswith("8") or code.startswith("4"):
        return "bj"
    return "sz"


def _get(row: Any, col: str) -> Any:
    try:
        return row[col]
    except KeyError:
        return None
