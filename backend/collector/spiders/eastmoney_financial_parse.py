"""东财三大报表解析层：报表期索引、字段映射抽取、落库行组装。

采集编排（akshare 拉取 + 写库）在 ``eastmoney_financial_statement``；
本模块为纯转换（pandas/标量进出，无 IO）。通用标量解析复用
``collector.core.parsing``。
"""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from collector.core.parsing import parse_date, to_decimal

DEFAULT_REPORT_TYPES = ["年报", "半年报", "一季报", "三季报"]

REPORT_TYPE_MAP = {
    "年报": "annual",
    "半年报": "semi",
    "中报": "semi",
    "一季报": "q1",
    "三季报": "q3",
}

BALANCE_SHEET_MAP: dict[str, str] = {
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

INCOME_STATEMENT_MAP: dict[str, list[str]] = {
    "total_revenue": ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME"],
    "operating_cost": ["TOTAL_OPERATE_COST", "OPERATE_COST", "OPERATE_EXPENSE"],
    "selling_expense": ["SALE_EXPENSE"],
    "admin_expense": ["MANAGE_EXPENSE"],
    "research_development_expense": ["RESEARCH_EXPENSE"],
    "finance_expense": ["FINANCE_EXPENSE"],
    "operating_profit": ["OPERATE_PROFIT"],
    "net_profit": ["NETPROFIT"],
    "net_profit_deducted": ["DEDUCT_PARENT_NETPROFIT"],
    "eps": ["BASIC_EPS"],
}

CASH_FLOW_STATEMENT_MAP: dict[str, str] = {
    "cash_flow_from_operations": "NETCASH_OPERATE",
    "cash_flow_from_investing": "NETCASH_INVEST",
    "cash_flow_from_financing": "NETCASH_FINANCE",
    "net_cash_flow": "CCE_ADD",
}


def to_em_symbol(symbol: str) -> str | None:
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


def parse_report_date(value: Any) -> date | None:
    if isinstance(value, str):
        value = value.strip().split(" ")[0]
    return parse_date(value)


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.replace({np.nan: None})


def index_by_date(df: pd.DataFrame) -> dict[date, pd.Series]:
    if df.empty:
        return {}
    rows: dict[date, pd.Series] = {}
    for _, row in df.iterrows():
        report_date = parse_report_date(row.get("REPORT_DATE"))
        if report_date is not None:
            rows[report_date] = row
    return rows


def first_not_none(values: list[Any]) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def extract_section(
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
        result[target_key] = to_decimal(value)
    return result


def build_table_row(
    base: dict[str, Any],
    section: dict[str, Decimal | None],
) -> dict[str, Any] | None:
    row = {**base, **{k: v for k, v in section.items() if v is not None}}
    if any(k != "stock_code" and k != "report_date" and k != "report_type" for k in row):
        return row
    return None


def add_free_cash_flow(cash: dict[str, Any] | None) -> dict[str, Any] | None:
    if cash is None:
        return None
    if cash.get("free_cash_flow") is not None:
        return cash
    operations = cash.get("cash_flow_from_operations")
    invest_pay = cash.get("cash_flow_from_investing")
    if operations is not None and invest_pay is not None:
        cash["free_cash_flow"] = operations + invest_pay
    return cash
