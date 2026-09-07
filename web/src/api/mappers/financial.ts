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
    stockCode: dto.stockCode,
    reportDate: dto.reportDate,
    reportType: dto.reportType,
    totalAssets: dto.totalAssets,
    currentAssets: dto.currentAssets,
    cashEquivalents: dto.cashEquivalents,
    accountsReceivable: dto.accountsReceivable,
    inventory: dto.inventory,
    fixedAssets: dto.fixedAssets,
    intangibleAssets: dto.intangibleAssets,
    goodwill: dto.goodwill,
    totalLiabilities: dto.totalLiabilities,
    currentLiabilities: dto.currentLiabilities,
    longTermDebt: dto.longTermDebt,
    totalEquity: dto.totalEquity,
    paidInCapital: dto.paidInCapital,
    retainedEarnings: dto.retainedEarnings,
    createdAt: dto.createdAt,
  }
}

export function mapIncomeStatement(dto: ApiIncomeStatementResponse): IncomeStatement {
  return {
    stockCode: dto.stockCode,
    reportDate: dto.reportDate,
    reportType: dto.reportType,
    totalRevenue: dto.totalRevenue,
    operatingCost: dto.operatingCost,
    sellingExpense: dto.sellingExpense,
    adminExpense: dto.adminExpense,
    researchDevelopmentExpense: dto.researchDevelopmentExpense,
    financeExpense: dto.financeExpense,
    operatingProfit: dto.operatingProfit,
    netProfit: dto.netProfit,
    netProfitDeducted: dto.netProfitDeducted,
    eps: dto.eps,
    createdAt: dto.createdAt,
  }
}

export function mapCashFlowStatement(dto: ApiCashFlowStatementResponse): CashFlowStatement {
  return {
    stockCode: dto.stockCode,
    reportDate: dto.reportDate,
    reportType: dto.reportType,
    cashFlowFromOperations: dto.cashFlowFromOperations,
    cashFlowFromInvesting: dto.cashFlowFromInvesting,
    cashFlowFromFinancing: dto.cashFlowFromFinancing,
    netCashFlow: dto.netCashFlow,
    freeCashFlow: dto.freeCashFlow,
    createdAt: dto.createdAt,
  }
}

export function mapFinancialHealth(dto: ApiFinancialHealthResponse): FinancialHealth {
  return {
    stockCode: dto.stockCode,
    reportDate: dto.reportDate,
    reportType: dto.reportType,
    financialBalanceSheet: dto.financialBalanceSheet
      ? mapBalanceSheet(dto.financialBalanceSheet)
      : null,
    financialIncomeStatement: dto.financialIncomeStatement
      ? mapIncomeStatement(dto.financialIncomeStatement)
      : null,
    financialCashFlowStatement: dto.financialCashFlowStatement
      ? mapCashFlowStatement(dto.financialCashFlowStatement)
      : null,
    metrics: dto.metrics,
  }
}

export function mapFinancialHistory(dto: ApiFinancialHistoryResponse): FinancialHistory {
  return {
    stockCode: dto.stockCode,
    history: dto.history.map(mapFinancialHealth),
  }
}
