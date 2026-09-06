"""财务健康度业务服务。"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_balance_sheet import BalanceSheet
from app.models.financial_cash_flow_statement import CashFlowStatement
from app.models.financial_income_statement import IncomeStatement
from app.repositories.market import financial_statement_repository
from app.schemas.financial import (
    BalanceSheetResponse,
    CashFlowStatementResponse,
    FinancialHealthResponse,
    IncomeStatementResponse,
)
from app.utils.numeric import safe_divide


def _compute_metrics(
    balance: BalanceSheet | None,
    income: IncomeStatement | None,
    cash: CashFlowStatement | None,
) -> dict[str, Any]:
    """根据三张报表计算财务健康度指标。"""
    metrics: dict[str, Any] = {}
    if balance:
        metrics["debt_ratio"] = safe_divide(
            balance.total_liabilities, balance.total_assets
        )
        metrics["current_ratio"] = safe_divide(
            balance.current_assets, balance.current_liabilities
        )
    if income:
        revenue = income.total_revenue or Decimal("0")
        operating_cost = income.operating_cost or Decimal("0")
        net_profit = income.net_profit or Decimal("0")
        metrics["gross_margin"] = safe_divide(revenue - operating_cost, revenue)
        metrics["net_margin"] = safe_divide(net_profit, revenue)
    if balance and income:
        metrics["roe"] = safe_divide(
            income.net_profit or Decimal("0"), balance.total_equity
        )
    if income and cash:
        metrics["operating_cf_ratio"] = safe_divide(
            cash.cash_flow_from_operations,
            income.total_revenue or Decimal("0"),
        )
    return metrics


async def get_health(
    session: AsyncSession,
    stock_code: str,
    report_date: date | None = None,
) -> FinancialHealthResponse:
    """获取指定股票的最新财务健康度分析。

    Args:
        session: 数据库会话。
        stock_code: 股票代码。
        report_date: 指定报告期；为空时取三张表中最新的报告期。

    Returns:
        财务健康度响应对象。
    """
    balance = await financial_statement_repository.get_statement(
        session, BalanceSheet, stock_code, report_date
    )
    income = await financial_statement_repository.get_statement(
        session, IncomeStatement, stock_code, report_date
    )
    cash = await financial_statement_repository.get_statement(
        session, CashFlowStatement, stock_code, report_date
    )

    latest_date: date | None = None
    for statement in (balance, income, cash):
        if statement and (latest_date is None or statement.report_date > latest_date):
            latest_date = statement.report_date

    metrics = _compute_metrics(balance, income, cash)

    return FinancialHealthResponse(
        stock_code=stock_code,
        report_date=latest_date,
        report_type=balance.report_type if balance else None,
        financial_balance_sheet=BalanceSheetResponse.model_validate(balance) if balance else None,
        financial_income_statement=IncomeStatementResponse.model_validate(income) if income else None,
        financial_cash_flow_statement=CashFlowStatementResponse.model_validate(cash) if cash else None,
        metrics=metrics,
    )


async def get_health_history(
    session: AsyncSession,
    stock_code: str,
    limit: int = 8,
) -> list[FinancialHealthResponse]:
    """获取指定股票最近多个报告期的财务健康度分析。

    Args:
        session: 数据库会话。
        stock_code: 股票代码。
        limit: 返回的最大报告期数量。

    Returns:
        按报告期升序排列的财务健康度响应列表。
    """
    balances = await financial_statement_repository.list_statements(
        session, BalanceSheet, stock_code, limit
    )
    incomes = await financial_statement_repository.list_statements(
        session, IncomeStatement, stock_code, limit
    )
    cash_flows = await financial_statement_repository.list_statements(
        session, CashFlowStatement, stock_code, limit
    )

    by_date: dict[date, list[BalanceSheet | IncomeStatement | CashFlowStatement | None]] = {}
    for statement in balances:
        by_date.setdefault(statement.report_date, [None, None, None])[0] = statement
    for statement in incomes:
        by_date.setdefault(statement.report_date, [None, None, None])[1] = statement
    for statement in cash_flows:
        by_date.setdefault(statement.report_date, [None, None, None])[2] = statement

    history: list[FinancialHealthResponse] = []
    for report_date in sorted(by_date):
        balance, income, cash = by_date[report_date]
        metrics = _compute_metrics(balance, income, cash)
        report_type = None
        if balance:
            report_type = balance.report_type
        elif income:
            report_type = income.report_type
        elif cash:
            report_type = cash.report_type

        history.append(
            FinancialHealthResponse(
                stock_code=stock_code,
                report_date=report_date,
                report_type=report_type,
                financial_balance_sheet=BalanceSheetResponse.model_validate(balance) if balance else None,
                financial_income_statement=IncomeStatementResponse.model_validate(income) if income else None,
                financial_cash_flow_statement=CashFlowStatementResponse.model_validate(cash) if cash else None,
                metrics=metrics,
            )
        )

    return history
