/** llm_config.extra.capabilities 约定：视觉等能力标记。 */
export interface LLMConfigCapabilities {
  vision?: boolean
}

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
  vision?: boolean
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

/**
 * 采集任务名。任务清单由后端注册表派生（GET /admin/collector/tasks/catalog），
 * 禁止在前端另行硬编码任务列表。
 */
export type CollectorTaskName = string

export interface CollectorTaskCatalogItem {
  name: CollectorTaskName
  label: string
  dataType: string
  sources: string[]
  configParams: string[]
  runParams: string[]
}

export interface CollectorTaskCatalog {
  items: CollectorTaskCatalogItem[]
}

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
  tradeDate?: string | null
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
  broker: string | null
  rating: string | null
  pages: number | null
  industry: string | null
  hasSummary: boolean
}

export interface ResearchReportFilters {
  stockCode?: string
  q?: string
  broker?: string
  industry?: string
  startDate?: string
  endDate?: string
}

export interface ResearchReportFilterOptions {
  brokers: string[]
  industries: string[]
}

export interface FinancialReport {
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

export interface FinancialReportFilters {
  stockCode?: string
  q?: string
  reportType?: string
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
  researchDevelopmentExpense: number | null
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
  cashFlowFromOperations: number | null
  cashFlowFromInvesting: number | null
  cashFlowFromFinancing: number | null
  netCashFlow: number | null
  freeCashFlow: number | null
  createdAt: string
}

export interface FinancialHealth {
  stockCode: string
  reportDate: string | null
  reportType: string | null
  financialBalanceSheet: BalanceSheet | null
  financialIncomeStatement: IncomeStatement | null
  financialCashFlowStatement: CashFlowStatement | null
  metrics: Record<string, number | null>
}

export interface FinancialHistory {
  stockCode: string
  history: FinancialHealth[]
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
  createdAt: string
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

export interface TrackedIndexConfig {
  id: number
  indexCode: string
  indexName: string
  marketCategory: string
  dataSource: string
  sortOrder: number
  isEnabled: boolean
  latestClose: number | null
  latestChangePct: number | null
  latestTradeDate: string | null
  createdAt: string
  updatedAt: string
}

export interface TrackedIndexFormValues {
  indexCode: string
  indexName: string
  marketCategory: string
  dataSource: string
  sortOrder: number
  isEnabled: boolean
}

/** 已纳管 AI skill 清单项（管理页 Tab 与完成事件订阅的数据源）。 */
export interface AdminAiSkillInfo {
  skillId: string
  label: string
  eventType: string | null
}

/** 业务键的单个字段（如 交易日 / 股票代码 / 行业+版本）。 */
export interface AdminAiKeyField {
  name: string
  label: string
  value: string
}

/** AI 结果管理列表行：每个业务键最新一条生成记录的元信息。 */
export interface AdminAiResultItem {
  id: number
  skillId: string
  keyFields: AdminAiKeyField[]
  model: string | null
  latencyMs: number | null
  status: string
  createdAt: string
  historyCount: number
  regeneratePrompt: string | null
}

/** 单条生成记录详情：元信息 + 结构化输出全文。 */
export interface AdminAiResultDetail extends AdminAiResultItem {
  errorMsg: string | null
  structuredOutput: Record<string, unknown> | null
}

export interface AdminAiResultListParams {
  skillId: string
  status?: string
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}
