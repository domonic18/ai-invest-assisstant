export interface LLMConfig {
  id: number
  name: string
  provider: string
  baseUrl: string
  modelName: string
  apiKeyMasked: string
  isDefault: boolean
  isActive: boolean
  extra: Record<string, unknown>
  lastTestedAt: string | null
  lastTestStatus: string | null
  lastTestError: string | null
  createdAt: string
  updatedAt: string
}

export interface LLMConfigFormValues {
  name: string
  provider: string
  baseUrl: string
  modelName: string
  apiKey: string
  isDefault: boolean
  isActive: boolean
}

export interface LLMConfigTestResult {
  status: string
  detail: string
  testedAt: string
}

export interface CollectorChannelConfig {
  id: number
  source: string
  name: string
  baseUrl: string | null
  apiKeyMasked: string | null
  isEnabled: boolean
  supportedDataTypes: string[]
  extra: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export interface CollectorChannelConfigFormValues {
  source: string
  name: string
  baseUrl: string
  apiKey: string
  isEnabled: boolean
  supportedDataTypes: string[]
}

export type CollectorTaskName =
  | 'kline'
  | 'index-kline'
  | 'auction'
  | 'fund-flow'
  | 'news'
  | 'company-profile'
  | 'disclosure'
  | 'sector-fund-flow'
  | 'dragon-list'
  | 'research-report'
  | 'financial-report'
  | 'ipo-info'
  | 'fund-holdings'
  | 'macro'
  | 'stock-list'
  | 'limit-up-pool'
  | 'market-breadth'

export interface CollectorTaskChannel {
  source: string
  name: string
  isEnabled: boolean
}

export interface CollectorTaskRunOptions {
  preferredSource?: string | null
  symbols?: string[] | null
  period?: string | null
  startDate?: string | null
  endDate?: string | null
  sectorType?: string | null
  indicators?: string[] | null
  reportTypes?: string[] | null
  reportDate?: string | null
}

export interface CollectorLog {
  id: number
  taskName: string
  source: string | null
  status: string
  startedAt: string | null
  finishedAt: string | null
  recordsCount: number
  errorMsg: string | null
  metadata: Record<string, unknown> | null
}

export interface CollectorTaskOption {
  key: CollectorTaskName
  label: string
}

export interface ResearchReport {
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
}

export interface ResearchReportFilters {
  stockCode?: string
  q?: string
  startDate?: string
  endDate?: string
}

export interface SectorFundFlow {
  sectorCode: string
  sectorName: string
  sectorType: string
  tradeDate: string
  changePct: number | null
  mainNetInflow: number | null
  superLargeNet: number | null
  largeNet: number | null
  mediumNet: number | null
  smallNet: number | null
  topStockCode: string | null
  topStockName: string | null
  createdAt: string
}

export interface HotspotFilters {
  sectorType?: string
  tradeDate?: string
}

export interface BalanceSheet {
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

export interface IncomeStatement {
  stockCode: string
  reportDate: string
  reportType: string
  totalRevenue: number | null
  operatingCost: number | null
  sellingExpense: number | null
  adminExpense: number | null
  rdExpense: number | null
  financeExpense: number | null
  operatingProfit: number | null
  netProfit: number | null
  netProfitDeducted: number | null
  eps: number | null
  createdAt: string
}

export interface CashFlowStatement {
  stockCode: string
  reportDate: string
  reportType: string
  cfOperations: number | null
  cfInvesting: number | null
  cfFinancing: number | null
  netCashFlow: number | null
  freeCashFlow: number | null
  createdAt: string
}

export interface FinancialHealth {
  stockCode: string
  reportDate: string | null
  reportType: string | null
  balanceSheet: BalanceSheet | null
  incomeStatement: IncomeStatement | null
  cashFlowStatement: CashFlowStatement | null
  metrics: Record<string, number | null>
}

export interface AdminUser {
  id: number
  username: string
  email: string
  role: string
  isActive: boolean
  lastLoginAt: string | null
  createdAt: string
}

export interface AdminUserFormValues {
  username: string
  email: string
  password?: string
  role: string
  isActive: boolean
}

export interface AdminStock {
  id: number
  stockCode: string
  stockName: string
  market: string
  industryL1: string | null
  industryL2: string | null
  industryL3: string | null
  listingDate: string | null
  totalShares: number | null
  circulatingShares: number | null
  fullName: string | null
  createdAt: string
}

export interface AdminStockFormValues {
  stockCode: string
  stockName: string
  market: string
  industryL1?: string
  industryL2?: string
  industryL3?: string
  listingDate?: string
}

export interface AdminReport {
  id: number
  filePath: string
  originalName: string | null
  fileType: string
  stockCode: string | null
  stockName: string | null
  reportDate: string | null
  reportType: string | null
  broker: string | null
  fileSize: number | null
  md5Hash: string | null
  downloadUrl: string | null
  downloadCount: number
  uploadedAt: string
}

export interface AdminReportFormValues {
  filePath: string
  originalName?: string
  fileType: string
  stockCode?: string
  reportDate?: string
  reportType?: string
  broker?: string
  fileSize?: number
  md5Hash?: string
  downloadUrl?: string
}

export interface AdminNews {
  id: number
  stockCode: string | null
  docType: string
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
}

export interface AdminNewsFormValues {
  stockCode?: string
  docType: string
  title: string
  summary?: string
  content?: string
  source?: string
  sourceUrl?: string
  publishDate?: string
  sentiment?: number
  keywords?: string[]
  industryTags?: string[]
  extra?: Record<string, unknown>
}

export interface AdminTask {
  id: number
  taskName: string
  taskType: string
  source: string
  schedule: string | null
  isActive: boolean
  lastRunAt: string | null
  lastStatus: string
  lastError: string | null
  createdAt: string
  updatedAt: string
}

export interface AdminTaskFormValues {
  taskName: string
  taskType: string
  source: string
  schedule?: string
  isActive: boolean
}

export interface CollectorDataTypeChannel {
  channelId: number
  source: string
  name: string
  isEnabled: boolean
  priority: number
}

export interface CollectorDataTypeChannels {
  dataType: string
  channels: CollectorDataTypeChannel[]
}
