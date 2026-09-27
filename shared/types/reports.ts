/** 研报 wire 类型（对应 services/reports 子域）。 */
export interface ApiResearchReportResponse {
  id: number
  stockCode: string | null
  title: string
  summary: string | null
  content: string | null
  source: string | null
  sourceUrl: string | null
  publishDate: string | null
  sentiment: number | null
  keywords: string[] | null
  industryTags: string[] | null
  extra: Record<string, unknown>
  createdAt: string
  broker: string | null
  rating: string | null
  pages: number | null
  industry: string | null
  hasSummary: boolean
}

export interface ApiResearchReportFiltersResponse {
  brokers: string[]
  industries: string[]
}

export interface ApiResearchSummarizeResponse {
  summary: string
  cached: boolean
}

/** 列表 query 参数（snake_case 跟随后端 FastAPI 签名）。 */
export interface ApiResearchReportListRequest {
  stock_code?: string | null
  q?: string | null
  start_date?: string | null
  end_date?: string | null
  page?: number
  page_size?: number
}

/** 财报文档 wire 类型。 */
export interface ApiFinancialReportResponse {
  id: number
  stockCode: string | null
  stockName: string | null
  title: string | null
  reportType: string | null
  reportDate: string | null
  fileSize: number | null
  summary: string | null
  hasSummary: boolean
  createdAt: string
}

export interface ApiFinancialSummarizeResponse {
  summary: string
  cached: boolean
}

export interface ApiFinancialReportCollectRequest {
  stockCode: string
  reportTypes?: string[] | null
  startDate?: string | null
  endDate?: string | null
}

export interface ApiFinancialReportCollectResponse {
  logId: number
  status: string
}

export interface ApiFinancialReportCollectLogResponse {
  logId: number
  status: string
  recordsCount: number
  errorMsg: string | null
  finishedAt: string | null
}

/** 三大报表与财务体检 wire 类型。 */
export interface ApiBalanceSheetResponse {
  stockCode: string
  reportDate: string
  reportType: string
  totalAssets: number | null
  currentAssets: number | null
  cashEquivalents: number | null
  accountsReceivable: number | null
  inventory: number | null
  fixedAssets: number | null
  intangibleAssets: number | null
  goodwill: number | null
  totalLiabilities: number | null
  currentLiabilities: number | null
  longTermDebt: number | null
  totalEquity: number | null
  paidInCapital: number | null
  retainedEarnings: number | null
  createdAt: string
}

export interface ApiIncomeStatementResponse {
  stockCode: string
  reportDate: string
  reportType: string
  totalRevenue: number | null
  operatingCost: number | null
  sellingExpense: number | null
  adminExpense: number | null
  researchDevelopmentExpense: number | null
  financeExpense: number | null
  operatingProfit: number | null
  netProfit: number | null
  netProfitDeducted: number | null
  eps: number | null
  createdAt: string
}

export interface ApiCashFlowStatementResponse {
  stockCode: string
  reportDate: string
  reportType: string
  cashFlowFromOperations: number | null
  cashFlowFromInvesting: number | null
  cashFlowFromFinancing: number | null
  netCashFlow: number | null
  freeCashFlow: number | null
  createdAt: string
}

export interface ApiFinancialHealthResponse {
  stockCode: string
  reportDate: string | null
  reportType: string | null
  financialBalanceSheet: ApiBalanceSheetResponse | null
  financialIncomeStatement: ApiIncomeStatementResponse | null
  financialCashFlowStatement: ApiCashFlowStatementResponse | null
  metrics: Record<string, number | null>
}

export interface ApiFinancialHistoryResponse {
  stockCode: string
  history: ApiFinancialHealthResponse[]
}
