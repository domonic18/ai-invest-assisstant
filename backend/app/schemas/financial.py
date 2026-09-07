"""财务健康度分析的 Pydantic schemas。"""

from datetime import date, datetime
from typing import Any

from pydantic import Field

from app.schemas.base import CamelModel


class BalanceSheetResponse(CamelModel):
    """资产负债表响应。"""

    stock_code: str
    report_date: date
    report_type: str
    total_assets: float | None = None
    current_assets: float | None = None
    cash_equivalents: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    fixed_assets: float | None = None
    intangible_assets: float | None = None
    goodwill: float | None = None
    total_liabilities: float | None = None
    current_liabilities: float | None = None
    long_term_debt: float | None = None
    total_equity: float | None = None
    paid_in_capital: float | None = None
    retained_earnings: float | None = None
    created_at: datetime


class IncomeStatementResponse(CamelModel):
    """利润表响应。"""

    stock_code: str
    report_date: date
    report_type: str
    total_revenue: float | None = None
    operating_cost: float | None = None
    selling_expense: float | None = None
    admin_expense: float | None = None
    research_development_expense: float | None = None
    finance_expense: float | None = None
    operating_profit: float | None = None
    net_profit: float | None = None
    net_profit_deducted: float | None = None
    eps: float | None = None
    created_at: datetime


class CashFlowStatementResponse(CamelModel):
    """现金流量表响应。"""

    stock_code: str
    report_date: date
    report_type: str
    cash_flow_from_operations: float | None = None
    cash_flow_from_investing: float | None = None
    cash_flow_from_financing: float | None = None
    net_cash_flow: float | None = None
    free_cash_flow: float | None = None
    created_at: datetime


class FinancialHealthResponse(CamelModel):
    """财务健康度综合响应。"""

    stock_code: str
    report_date: date | None = None
    report_type: str | None = None
    financial_balance_sheet: BalanceSheetResponse | None = None
    financial_income_statement: IncomeStatementResponse | None = None
    financial_cash_flow_statement: CashFlowStatementResponse | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class FinancialHealthRequest(CamelModel):
    """财务健康度请求。"""

    report_date: date | None = None


class FinancialHistoryResponse(CamelModel):
    """财务历史趋势响应。"""

    stock_code: str
    history: list[FinancialHealthResponse]
