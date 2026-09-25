/** llm_config.extra.capabilities 约定：视觉等能力标记。 */
export interface LLMConfigCapabilities {
  vision?: boolean
}

/** LLM 接口协议：openai 兼容 / anthropic 原生。 */
export type LLMProtocol = 'openai' | 'anthropic'

export interface LLMConfig {
  id: number
  name: string
  provider: string
  protocol: LLMProtocol
  baseUrl: string
  modelName: string
  apiKeyMasked: string
  isDefault: boolean
  isActive: boolean
  purpose: LlmPurpose
  /** 备用配置 id：本配置额度耗尽冷却期内自动切换的目标（单级） */
  backupConfigId: number | null
  /** 额度耗尽冷却截止时间；null 表示健康 */
  degradedUntil: string | null
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
  protocol: LLMProtocol
  baseUrl: string
  modelName: string
  apiKey: string
  isDefault: boolean
  isActive: boolean
  purpose: LlmPurpose
  backupConfigId?: number | null
  vision?: boolean
}

export interface LLMConfigTestResult {
  status: string
  detail: string
  testedAt: string
}

/** 配置用途（知识库模型角色槽位按此过滤候选） */
export type LlmPurpose = 'chat' | 'embedding' | 'vision'

export interface ApiLLMConfigResponse {
  id: number
  name: string
  provider: string
  protocol: string
  baseUrl: string
  modelName: string
  apiKeyMasked: string
  isDefault: boolean
  isActive: boolean
  purpose: LlmPurpose
  backupConfigId: number | null
  degradedUntil: string | null
  extra: Record<string, unknown>
  lastTestedAt: string | null
  lastTestStatus: string | null
  lastTestError: string | null
  createdAt: string
  updatedAt: string
}

export interface ApiLLMConfigCreateRequest {
  name: string
  provider: string
  protocol?: string
  baseUrl: string
  apiKey: string
  modelName: string
  isDefault?: boolean
  isActive?: boolean
  purpose?: LlmPurpose
  backupConfigId?: number | null
  extra?: Record<string, unknown>
}

export interface ApiLLMConfigUpdateRequest {
  name?: string
  provider?: string
  protocol?: string
  baseUrl?: string
  apiKey?: string
  modelName?: string
  isDefault?: boolean
  isActive?: boolean
  purpose?: LlmPurpose
  backupConfigId?: number | null
  extra?: Record<string, unknown>
}

export interface ApiLLMConfigTestResponse {
  status: string
  detail: string
  testedAt: string
}

/** ASR 渠道配置 masked 视图（密钥只回脱敏串）。 */
export interface ApiAsrConfig {
  provider: string
  baseUrl: string
  model: string
  apiKeyMasked: string | null
  apiKeyConfigured: boolean
  maxAudioSeconds: number
  hotwords: string[]
  enabled: boolean
  updatedAt: string
}

/** 更新 ASR 配置（apiKey write-only：留空保留原值）。 */
export interface ApiAsrConfigUpdateRequest {
  provider?: string
  baseUrl?: string
  model?: string
  apiKey?: string
  maxAudioSeconds?: number
  hotwords?: string[]
  enabled?: boolean
}

/** ASR 连接测试结果。 */
export interface ApiAsrConfigTestResult {
  ok: boolean
  latencyMs: number
  text: string | null
  error: string | null
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
  proxyConfigId: number | null
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
  proxyConfigId?: number | null
}

/** 代理服务器配置（密码已脱敏）。 */
export interface ProxyConfig {
  id: number
  name: string
  protocol: 'http' | 'socks5'
  host: string
  port: number
  username: string | null
  passwordMasked: string | null
  isEnabled: boolean
  createdAt: string
  updatedAt: string
}

/** password 留空表示不修改已存储的密码。 */
export interface ProxyConfigFormValues {
  name: string
  protocol: 'http' | 'socks5'
  host: string
  port: number
  username?: string
  password: string
  isEnabled: boolean
}

export interface ProxyTestResult {
  ok: boolean
  statusCode: number | null
  latencyMs: number
  error: string | null
}

/**
 * 采集任务名。任务清单由后端注册表派生（GET /admin/collector/tasks/catalog），
 * 禁止在前端另行硬编码任务列表。
 */
export type CollectorTaskName = string

export interface CollectorTaskCatalogItem {
  name: CollectorTaskName
  label: string
  description: string
  dataType: string
  sources: string[]
  configParams: string[]
  runParams: string[]
  defaults: Record<string, unknown>
}

export interface CollectorTaskCatalog {
  items: CollectorTaskCatalogItem[]
}

/** 单渠道调试采集请求（只采集不落库）。 */
export interface CollectorChannelDebugRequest {
  dataType: string
  symbols?: string[] | null
  params?: Record<string, unknown>
}

/** 单渠道调试采集结果：样例上限 3 条，绝不携带渠道凭据。 */
export interface CollectorChannelDebugResult {
  ok: boolean
  errorKind: 'no_collector' | 'disabled' | 'timeout' | 'error' | null
  error: string | null
  durationMs: number
  collected: number
  sampleValid: number | null
  sampleItems: Record<string, unknown>[]
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
  message?: string | null
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
  status: string
  applicationNote: string | null
  rejectReason: string | null
  lastLoginAt: string | null
  createdAt: string
  remainingQuota: number | null
  totalUsed: number
  byokEnabled: boolean
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

export interface AdminTelegraph {
  id: number
  title: string | null
  content: string | null
  category: string | null
  importance: number | null
  stockCodes: string[] | null
  publishTime: string
  aiScore: number | null
  aiScoredAt: string | null
}

export interface AdminTask {
  id: number
  taskName: string
  taskType: string
  source: string
  remark: string | null
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
  remark?: string
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

/** 单个依赖服务的连通性探测结果。 */
export interface ServiceStatusItem {
  key: string
  name: string
  category: 'storage' | 'compute' | 'external'
  status: 'up' | 'down'
  latencyMs: number | null
  detail: string | null
  error: string | null
}

/** 系统服务状态汇总（后台「服务状态」页）。 */
export interface SystemStatus {
  overall: 'operational' | 'degraded'
  items: ServiceStatusItem[]
  checkedAt: string
}

/** Celery 任务方框状态：排队/执行中/终态。 */
export type CeleryTaskState = 'pending' | 'running' | 'success' | 'partial' | 'failed' | 'skipped'

/** 方框网格中的单个任务（一框一任务实例）。 */
export interface CeleryTaskSquare {
  key: string
  taskType: string
  label: string
  state: CeleryTaskState
  source: string | null
  startedAt: string | null
  finishedAt: string | null
  durationMs: number | null
  detail: string | null
}

/** 单个 Celery 队列的任务方框集合。 */
export interface CeleryQueueStatus {
  name: string
  label: string
  pendingTotal: number
  tasks: CeleryTaskSquare[]
}

/** 三队列任务状态总览；brokerOk=false 表示 broker 不可达（仅 DB 侧数据）。 */
export interface CeleryQueues {
  brokerOk: boolean
  queues: CeleryQueueStatus[]
  checkedAt: string
}

export interface ApiAdminUserResponse {
  id: number
  username: string
  email: string
  role: string
  isActive: boolean
  status: string
  applicationNote: string | null
  rejectReason: string | null
  lastLoginAt: string | null
  createdAt: string
  remainingQuota: number | null
  totalUsed: number
  byokEnabled: boolean
}

export interface ApiAdminUserCreateRequest {
  username: string
  email: string
  password: string
  role?: string
  isActive?: boolean
}

export interface ApiAdminUserUpdateRequest {
  username?: string
  email?: string
  role?: string
  isActive?: boolean
}

export interface ApiAdminUserResetPasswordRequest {
  password: string
}

export interface ApiAdminStockResponse {
  id: number
  stockCode: string
  stockName: string
  market: string
  industryLevel1: string | null
  industryLevel2: string | null
  industryLevel3: string | null
  listingDate: string | null
  totalShares: number | null
  circulatingShares: number | null
  fullName: string | null
  createdAt: string
}

export interface ApiAdminStockCreateRequest {
  stockCode: string
  stockName: string
  market: string
  industryLevel1?: string
  industryLevel2?: string
  industryLevel3?: string
  listingDate?: string
}

export interface ApiAdminStockUpdateRequest {
  stockName?: string
  market?: string
  industryLevel1?: string
  industryLevel2?: string
  industryLevel3?: string
  listingDate?: string
}

export interface ApiAdminReportResponse {
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

export interface ApiAdminReportCreateRequest {
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

export interface ApiAdminReportUpdateRequest {
  originalName?: string
  fileType?: string
  stockCode?: string
  reportDate?: string
  reportType?: string
  broker?: string
  fileSize?: number
  md5Hash?: string
  downloadUrl?: string
}

export interface ApiReportStorageTypeSummary {
  fileType: string
  fileCount: number
  sizeBytes: number
}

export interface ApiReportStorageSummary {
  items: ApiReportStorageTypeSummary[]
  totalSizeBytes: number
  totalFileCount: number
}

export interface ApiReportCleanupResult {
  removedCount: number
  sizeBytes: number
}

export interface ApiAdminNewsResponse {
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

export interface ApiAdminNewsCreateRequest {
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

export interface ApiAdminNewsUpdateRequest {
  stockCode?: string
  docType?: string
  title?: string
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

export interface ApiAdminTelegraphResponse {
  id: number
  title: string | null
  content: string | null
  category: string | null
  importance: number | null
  stockCodes: string[] | null
  publishTime: string
  aiScore: number | null
  aiScoredAt: string | null
}

export interface ApiAdminTaskResponse {
  id: number
  taskName: string
  taskType: string
  source: string
  remark: string | null
  schedule: string | null
  isActive: boolean
  lastRunAt: string | null
  lastStatus: string
  lastError: string | null
  createdAt: string
  updatedAt: string
}

export interface ApiAdminTaskCreateRequest {
  taskName: string
  taskType: string
  source: string
  remark?: string | null
  schedule?: string
  isActive?: boolean
}

export interface ApiAdminTaskUpdateRequest {
  taskType?: string
  source?: string
  remark?: string | null
  schedule?: string
  isActive?: boolean
}

export interface ApiDataTypeChannelItem {
  channelId: number
  source: string
  name: string
  isEnabled: boolean
  priority: number
}

export interface ApiDataTypeChannelsResponse {
  dataType: string
  channels: ApiDataTypeChannelItem[]
}

export interface ApiDataTypeChannelPriorityInput {
  channelId: number
  priority: number
}

export interface ApiTrackedIndexResponse {
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

export interface ApiTrackedIndexCreateRequest {
  indexCode: string
  indexName: string
  marketCategory: string
  dataSource: string
  sortOrder?: number
  isEnabled?: boolean
}

export interface ApiTrackedIndexUpdateRequest {
  indexName?: string
  marketCategory?: string
  dataSource?: string
  sortOrder?: number
  isEnabled?: boolean
}

export interface ApiTrackedIndexToggleResponse {
  id: number
  isEnabled: boolean
}

export interface ApiAdminAiSkillInfo {
  skillId: string
  label: string
  eventType: string | null
}

export interface ApiAdminAiResultKeyField {
  name: string
  label: string
  value: string
}

export interface ApiAdminAiResultItem {
  id: number
  skillId: string
  keyFields: ApiAdminAiResultKeyField[]
  model: string | null
  latencyMs: number | null
  status: string
  createdAt: string
  historyCount: number
  regeneratePrompt: string | null
}

export interface ApiAdminAiResultDetail extends ApiAdminAiResultItem {
  errorMsg: string | null
  structuredOutput: Record<string, unknown> | null
}
