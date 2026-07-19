"""EastMoney financial statement collector via akshare."""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from collector.core.base import BaseCollector, get_engine
from collector.core.exporters import PostgresExporter
from collector.core.parsing import clean_stock_code, parse_date, to_optional_str

DEFAULT_REPORT_TYPES = ["年报", "半年报", "一季报", "三季报"]

_REPORT_TYPE_MAP = {
    "年报": "annual",
    "半年报": "semi",
    "中报": "semi",
    "一季报": "q1",
    "三季报": "q3",
}

_BALANCE_SHEET_MAP: dict[str, str] = {
    "total_assets": "TOTAL_ASSETS",
    "current_assets": "TOTAL_CURRENT_ASSETS",
    "cash_equivalents": "MONETARYFUNDS",
    "accounts_receivable": "ACCOUNTS_RECE",
    "inventory": "INVENTORY",
    "fixed_assets": "FIXED_ASSET",
    "intangible_assets": "INTANGIBLE_ASSET",
    "goodwill": "GOODWILL",
    "total_liabilities": "TOTAL_LIABILITIES",
    "current_liabilities": "TOTAL_CURRENT_LIAB",
    "long_term_debt": "LONG_DEBT",
    "total_equity": "TOTAL_EQUITY",
    "paid_in_capital": "SHARE_CAPITAL",
    "retained_earnings": "UNASSIGN_RPOFIT",
}

_INCOME_STATEMENT_MAP: dict[str, list[str]] = {
    "total_revenue": ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME"],
    "operating_cost": ["TOTAL_OPERATE_COST", "OPERATE_COST", "OPERATE_EXPENSE"],
    "selling_expense": ["SALE_EXPENSE"],
    "admin_expense": ["MANAGE_EXPENSE"],
    "rd_expense": ["RESEARCH_EXPENSE"],
    "finance_expense": ["FINANCE_EXPENSE"],
    "operating_profit": ["OPERATE_PROFIT"],
    "net_profit": ["NETPROFIT"],
    "net_profit_deducted": ["DEDUCT_PARENT_NETPROFIT"],
    "eps": ["BASIC_EPS"],
}

_CASH_FLOW_STATEMENT_MAP: dict[str, str] = {
    "cf_operations": "NETCASH_OPERATE",
    "cf_investing": "NETCASH_INVEST",
    "cf_financing": "NETCASH_FINANCE",
    "net_cash_flow": "CCE_ADD",
}


class EastmoneyFinancialStatementCollector(BaseCollector):
    """东方财富个股三大报表采集器，写入 balance_sheet / income_statement / cash_flow_statement。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.report_types = config.get("report_types") or DEFAULT_REPORT_TYPES
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")

    async def collect(
        self,
        symbols: list[str] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        allowed_report_types = set(self.report_types or DEFAULT_REPORT_TYPES)
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            em_symbol = _to_em_symbol(symbol)
            if not em_symbol:
                continue

            try:
                balance_df = ak.stock_balance_sheet_by_report_em(symbol=em_symbol)
                income_df = ak.stock_profit_sheet_by_report_em(symbol=em_symbol)
                cash_df = ak.stock_cash_flow_sheet_by_report_em(symbol=em_symbol)
            except Exception:  # noqa: BLE001
                continue

            balance_df = _normalize_df(balance_df)
            income_df = _normalize_df(income_df)
            cash_df = _normalize_df(cash_df)

            if balance_df.empty and income_df.empty and cash_df.empty:
                continue

            balance_rows = _index_by_date(balance_df)
            income_rows = _index_by_date(income_df)
            cash_rows = _index_by_date(cash_df)

            all_dates = set(balance_rows.keys()) | set(income_rows.keys()) | set(cash_rows.keys())
            all_dates.discard(None)

            for report_date in sorted(all_dates, reverse=True):
                original_type = _first_not_none(
                    [
                        _str(balance_rows.get(report_date, {}).get("REPORT_TYPE")),
                        _str(income_rows.get(report_date, {}).get("REPORT_TYPE")),
                        _str(cash_rows.get(report_date, {}).get("REPORT_TYPE")),
                    ]
                )
                if original_type is None:
                    continue
                if allowed_report_types and original_type not in allowed_report_types:
                    continue

                report_type = _REPORT_TYPE_MAP.get(original_type)
                if report_type is None:
                    continue

                raw.append(
                    {
                        "stock_code": _clean_code(symbol),
                        "report_date": report_date,
                        "report_type": report_type,
                        "balance": _extract_section(balance_rows.get(report_date), _BALANCE_SHEET_MAP),
                        "income": _extract_section(income_rows.get(report_date), _INCOME_STATEMENT_MAP),
                        "cash": _extract_section(cash_rows.get(report_date), _CASH_FLOW_STATEMENT_MAP),
                    }
                )

        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "report_date": raw["report_date"],
            "report_type": raw["report_type"],
            "balance": raw.get("balance") or {},
            "income": raw.get("income") or {},
            "cash": raw.get("cash") or {},
            "source": self.source,
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        if not item.get("stock_code") or not item.get("report_date") or not item.get("report_type"):
            return False
        return any(
            (item.get(section) or {}) for section in ("balance", "income", "cash")
        )

    async def store(self, items: list[dict[str, Any]]) -> int:
        if not items:
            return 0

        balance_items: list[dict[str, Any]] = []
        income_items: list[dict[str, Any]] = []
        cash_items: list[dict[str, Any]] = []

        for item in items:
            base = {
                "stock_code": item["stock_code"],
                "report_date": item["report_date"],
                "report_type": item["report_type"],
            }
            balance = _build_table_row(base, item.get("balance") or {})
            income = _build_table_row(base, item.get("income") or {})
            cash = _build_table_row(base, item.get("cash") or {})
            cash = _add_free_cash_flow(cash)

            if balance:
                balance_items.append(balance)
            if income:
                income_items.append(income)
            if cash:
                cash_items.append(cash)

        if not balance_items and not income_items and not cash_items:
            return 0

        session_maker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
        total = 0
        async with session_maker() as session:
            exporter = PostgresExporter(session)
            if balance_items:
                total += await exporter.insert_many(
                    "balance_sheet",
                    balance_items,
                    conflict_key="stock_code, report_date",
                )
            if income_items:
                total += await exporter.insert_many(
                    "income_statement",
                    income_items,
                    conflict_key="stock_code, report_date",
                )
            if cash_items:
                total += await exporter.insert_many(
                    "cash_flow_statement",
                    cash_items,
                    conflict_key="stock_code, report_date",
                )
        return total


def _to_em_symbol(symbol: str) -> str | None:
    code = symbol.strip().lower()
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith(("0", "2", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8", "9")):
        return f"bj{code}"
    return None


_clean_code = clean_stock_code


_str = to_optional_str


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return None if number != number else number  # NaN check


def _parse_date(value: Any) -> date | None:
    if isinstance(value, str):
        value = value.strip().split(" ")[0]
    return parse_date(value)


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.replace({np.nan: None})


def _index_by_date(df: pd.DataFrame) -> dict[date, pd.Series]:
    if df.empty:
        return {}
    rows: dict[date, pd.Series] = {}
    for _, row in df.iterrows():
        report_date = _parse_date(row.get("REPORT_DATE"))
        if report_date is not None:
            rows[report_date] = row
    return rows


def _first_not_none(values: list[Any]) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _extract_section(
    row: pd.Series | None,
    mapping: Mapping[str, str | Sequence[str]],
) -> dict[str, Decimal | None]:
    if row is None:
        return {}
    result: dict[str, Decimal | None] = {}
    for target_key, source_keys in mapping.items():
        if isinstance(source_keys, str):
            source_keys = [source_keys]
        value = None
        for key in source_keys:
            if key in row:
                value = row[key]
                break
        result[target_key] = _to_decimal(value)
    return result


def _build_table_row(
    base: dict[str, Any],
    section: dict[str, Decimal | None],
) -> dict[str, Any] | None:
    row = {**base, **{k: v for k, v in section.items() if v is not None}}
    if any(k != "stock_code" and k != "report_date" and k != "report_type" for k in row):
        return row
    return None


def _add_free_cash_flow(cash: dict[str, Any] | None) -> dict[str, Any] | None:
    if cash is None:
        return None
    if cash.get("free_cash_flow") is not None:
        return cash
    operations = cash.get("cf_operations")
    invest_pay = cash.get("cf_investing")
    if operations is not None and invest_pay is not None:
        cash["free_cash_flow"] = operations + invest_pay
    return cash
