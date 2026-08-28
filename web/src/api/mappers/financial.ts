import type {
  ApiBalanceSheetResponse,
  ApiCashFlowStatementResponse,
  ApiFinancialHealthResponse,
  ApiFinancialHistoryResponse,
  ApiIncomeStatementResponse,
} from '@ai-invest/shared'
import type {
  BalanceSheet,
  CashFlowStatement,
  FinancialHealth,
  FinancialHistory,
  IncomeStatement,
} from '@ai-invest/shared'

export function mapBalanceSheet(dto: ApiBalanceSheetResponse): BalanceSheet {
  return {
    stockCode: dto.stock_code,
    reportDate: dto.report_date,
    reportType: dto.report_type,
    totalAssets: dto.total_assets,
    currentAssets: dto.current_assets,
    cashEquivalents: dto.cash_equivalents,
    accountsReceivable: dto.accounts_receivable,
    inventory: dto.inventory,
    fixedAssets: dto.fixed_assets,
    intangibleAssets: dto.intangible_assets,
    goodwill: dto.goodwill,
    totalLiabilities: dto.total_liabilities,
    currentLiabilities: dto.current_liabilities,
    longTermDebt: dto.long_term_debt,
    totalEquity: dto.total_equity,
    paidInCapital: dto.paid_in_capital,
    retainedEarnings: dto.retained_earnings,
    createdAt: dto.created_at,
  }
}

export function mapIncomeStatement(dto: ApiIncomeStatementResponse): IncomeStatement {
  return {
    stockCode: dto.stock_code,
    reportDate: dto.report_date,
    reportType: dto.report_type,
    totalRevenue: dto.total_revenue,
    operatingCost: dto.operating_cost,
    sellingExpense: dto.selling_expense,
    adminExpense: dto.admin_expense,
    researchDevelopmentExpense: dto.research_development_expense,
    financeExpense: dto.finance_expense,
    operatingProfit: dto.operating_profit,
    netProfit: dto.net_profit,
    netProfitDeducted: dto.net_profit_deducted,
    eps: dto.eps,
    createdAt: dto.created_at,
  }
}

export function mapCashFlowStatement(dto: ApiCashFlowStatementResponse): CashFlowStatement {
  return {
    stockCode: dto.stock_code,
    reportDate: dto.report_date,
    reportType: dto.report_type,
    cashFlowFromOperations: dto.cash_flow_from_operations,
    cashFlowFromInvesting: dto.cash_flow_from_investing,
    cashFlowFromFinancing: dto.cash_flow_from_financing,
    netCashFlow: dto.net_cash_flow,
    freeCashFlow: dto.free_cash_flow,
    createdAt: dto.created_at,
  }
}

export function mapFinancialHealth(dto: ApiFinancialHealthResponse): FinancialHealth {
  return {
    stockCode: dto.stock_code,
    reportDate: dto.report_date,
    reportType: dto.report_type,
    financialBalanceSheet: dto.financial_balance_sheet
      ? mapBalanceSheet(dto.financial_balance_sheet)
      : null,
    financialIncomeStatement: dto.financial_income_statement
      ? mapIncomeStatement(dto.financial_income_statement)
      : null,
    financialCashFlowStatement: dto.financial_cash_flow_statement
      ? mapCashFlowStatement(dto.financial_cash_flow_statement)
      : null,
    metrics: dto.metrics,
  }
}

export function mapFinancialHistory(dto: ApiFinancialHistoryResponse): FinancialHistory {
  return {
    stockCode: dto.stock_code,
    history: dto.history.map(mapFinancialHealth),
  }
}
