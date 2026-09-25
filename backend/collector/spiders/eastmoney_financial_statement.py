"""基于 akshare 的东方财富财务报表采集器。

解析层（报表期索引/字段映射抽取/落库行组装）在 ``eastmoney_financial_parse``；
本模块只做采集编排：akshare 拉取三大报表 → 按报表期对齐 → 写三张财务表。
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from collector.core.base import BaseCollector, get_engine
from collector.core.exporters import PostgresExporter
from collector.core.parsing import clean_stock_code, to_optional_str
from collector.spiders.eastmoney_financial_parse import (
    BALANCE_SHEET_MAP,
    CASH_FLOW_STATEMENT_MAP,
    DEFAULT_REPORT_TYPES,
    INCOME_STATEMENT_MAP,
    REPORT_TYPE_MAP,
    add_free_cash_flow,
    build_table_row,
    extract_section,
    first_not_none,
    index_by_date,
    normalize_df,
    to_em_symbol,
)
from collector.spiders.sina_kline import _fetch_watchlist_codes


class EastmoneyFinancialStatementCollector(BaseCollector):
    """东方财富个股三大报表采集器，写入 financial_balance_sheet / financial_income_statement / financial_cash_flow_statement。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.report_types = config.get("report_types") or DEFAULT_REPORT_TYPES
        self.api_key = config.get("api_key")

    async def collect(
        self,
        symbols: list[str] | None = None,
        items: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        # run(items=...) 手动注入已采集数据（测试/回放），跳过真实采集
        if items is not None:
            return items

        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or await _fetch_watchlist_codes()
        allowed_report_types = set(self.report_types or DEFAULT_REPORT_TYPES)
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            em_symbol = to_em_symbol(symbol)
            if not em_symbol:
                continue

            try:
                balance_df = ak.stock_balance_sheet_by_report_em(symbol=em_symbol)
                income_df = ak.stock_profit_sheet_by_report_em(symbol=em_symbol)
                cash_df = ak.stock_cash_flow_sheet_by_report_em(symbol=em_symbol)
            except Exception:  # noqa: BLE001
                continue

            balance_df = normalize_df(balance_df)
            income_df = normalize_df(income_df)
            cash_df = normalize_df(cash_df)

            if balance_df.empty and income_df.empty and cash_df.empty:
                continue

            balance_rows = index_by_date(balance_df)
            income_rows = index_by_date(income_df)
            cash_rows = index_by_date(cash_df)

            all_dates = set(balance_rows.keys()) | set(income_rows.keys()) | set(cash_rows.keys())
            all_dates.discard(None)

            for report_date in sorted(all_dates, reverse=True):
                original_type = first_not_none(
                    [
                        to_optional_str(balance_rows.get(report_date, {}).get("REPORT_TYPE")),
                        to_optional_str(income_rows.get(report_date, {}).get("REPORT_TYPE")),
                        to_optional_str(cash_rows.get(report_date, {}).get("REPORT_TYPE")),
                    ]
                )
                if original_type is None:
                    continue
                report_type = REPORT_TYPE_MAP.get(original_type)
                if report_type is None:
                    continue
                if allowed_report_types and original_type not in allowed_report_types:
                    continue

                raw.append(
                    {
                        "stock_code": clean_stock_code(symbol),
                        "report_date": report_date,
                        "report_type": report_type,
                        "balance": extract_section(balance_rows.get(report_date), BALANCE_SHEET_MAP),
                        "income": extract_section(income_rows.get(report_date), INCOME_STATEMENT_MAP),
                        "cash": extract_section(cash_rows.get(report_date), CASH_FLOW_STATEMENT_MAP),
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
            balance = build_table_row(base, item.get("balance") or {})
            income = build_table_row(base, item.get("income") or {})
            cash = add_free_cash_flow(build_table_row(base, item.get("cash") or {}))

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
            for table_name, rows in (
                ("financial_balance_sheet", balance_items),
                ("financial_income_statement", income_items),
                ("financial_cash_flow_statement", cash_items),
            ):
                if rows:
                    total += await exporter.insert_many(
                        table_name,
                        rows,
                        conflict_key="stock_code, report_date",
                    )
        return total
