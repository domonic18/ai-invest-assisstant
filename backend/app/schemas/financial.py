"""财务健康度分析的 Pydantic schemas。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BalanceSheetResponse(BaseModel):
    """资产负债表响应。"""

    model_config = ConfigDict(from_attributes=True)

    stock_code: str
    report_date: date
    report_type: str
    total_assets: Decimal | None = None
    current_assets: Decimal | None = None
    cash_equivalents: Decimal | None = None
    accounts_receivable: Decimal | None = None
    inventory: Decimal | None = None
    fixed_assets: Decimal | None = None
    intangible_assets: Decimal | None = None
    goodwill: Decimal | None = None
    total_liabilities: Decimal | None = None
    current_liabilities: Decimal | None = None
    long_term_debt: Decimal | None = None
    total_equity: Decimal | None = None
    paid_in_capital: Decimal | None = None
    retained_earnings: Decimal | None = None
    created_at: datetime


class IncomeStatementResponse(BaseModel):
    """利润表响应。"""

    model_config = ConfigDict(from_attributes=True)

    stock_code: str
    report_date: date
    report_type: str
    total_revenue: Decimal | None = None
    operating_cost: Decimal | None = None
    selling_expense: Decimal | None = None
    admin_expense: Decimal | None = None
    research_development_expense: Decimal | None = None
    finance_expense: Decimal | None = None
    operating_profit: Decimal | None = None
    net_profit: Decimal | None = None
    net_profit_deducted: Decimal | None = None
    eps: Decimal | None = None
    created_at: datetime


class CashFlowStatementResponse(BaseModel):
    """现金流量表响应。"""

    model_config = ConfigDict(from_attributes=True)

    stock_code: str
    report_date: date
    report_type: str
    cash_flow_from_operations: Decimal | None = None
    cash_flow_from_investing: Decimal | None = None
    cash_flow_from_financing: Decimal | None = None
    net_cash_flow: Decimal | None = None
    free_cash_flow: Decimal | None = None
    created_at: datetime


class FinancialHealthResponse(BaseModel):
    """财务健康度综合响应。"""

    model_config = ConfigDict(from_attributes=True)

    stock_code: str
    report_date: date | None = None
    report_type: str | None = None
    financial_balance_sheet: BalanceSheetResponse | None = None
    financial_income_statement: IncomeStatementResponse | None = None
    financial_cash_flow_statement: CashFlowStatementResponse | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class FinancialHealthRequest(BaseModel):
    """财务健康度请求。"""

    report_date: date | None = None


class FinancialHistoryResponse(BaseModel):
    """财务历史趋势响应。"""

    model_config = ConfigDict(from_attributes=True)

    stock_code: str
    history: list[FinancialHealthResponse]
