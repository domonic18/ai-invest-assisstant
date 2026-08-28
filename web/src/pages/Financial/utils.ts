import type { FinancialHealth } from '@ai-invest/shared'

export const statementColumns = [
  { title: '科目', dataIndex: 'label', key: 'label' },
  { title: '金额', dataIndex: 'value', key: 'value' },
]

export function renderPercent(value: number | null): string {
  return value === null ? '-' : `${(value * 100).toFixed(2)}%`
}

export function buildBalanceRows(data: FinancialHealth) {
  const bs = data.financialBalanceSheet
  if (!bs) return []
  return [
    { label: '总资产', value: bs.totalAssets },
    { label: '流动资产', value: bs.currentAssets },
    { label: '现金及等价物', value: bs.cashEquivalents },
    { label: '应收账款', value: bs.accountsReceivable },
    { label: '存货', value: bs.inventory },
    { label: '固定资产', value: bs.fixedAssets },
    { label: '无形资产', value: bs.intangibleAssets },
    { label: '商誉', value: bs.goodwill },
    { label: '总负债', value: bs.totalLiabilities },
    { label: '流动负债', value: bs.currentLiabilities },
    { label: '长期负债', value: bs.longTermDebt },
    { label: '所有者权益', value: bs.totalEquity },
  ].filter((row) => row.value !== null)
}

export function buildIncomeRows(data: FinancialHealth) {
  const inc = data.financialIncomeStatement
  if (!inc) return []
  return [
    { label: '营业收入', value: inc.totalRevenue },
    { label: '营业成本', value: inc.operatingCost },
    { label: '销售费用', value: inc.sellingExpense },
    { label: '管理费用', value: inc.adminExpense },
    { label: '研发费用', value: inc.researchDevelopmentExpense },
    { label: '财务费用', value: inc.financeExpense },
    { label: '营业利润', value: inc.operatingProfit },
    { label: '净利润', value: inc.netProfit },
    { label: '扣非净利润', value: inc.netProfitDeducted },
    { label: '每股收益', value: inc.eps },
  ].filter((row) => row.value !== null)
}

export function buildCashRows(data: FinancialHealth) {
  const cf = data.financialCashFlowStatement
  if (!cf) return []
  return [
    { label: '经营活动现金流', value: cf.cashFlowFromOperations },
    { label: '投资活动现金流', value: cf.cashFlowFromInvesting },
    { label: '筹资活动现金流', value: cf.cashFlowFromFinancing },
    { label: '净现金流', value: cf.netCashFlow },
    { label: '自由现金流', value: cf.freeCashFlow },
  ].filter((row) => row.value !== null)
}
