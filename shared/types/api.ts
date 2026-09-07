export interface ApiRegisterRequest {
  username: string
  email: string
  password: string
}

export interface ApiMovingAverageConfig {
  period: number
  color: string
  enabled: boolean
}

export interface ApiUserSettings {
  maConfigs: ApiMovingAverageConfig[]
}

export interface ApiUserSettingsUpdateRequest {
  maConfigs: ApiMovingAverageConfig[]
}

export interface ApiUserResponse {
  id: number
  username: string
  email: string
  role: string
  isActive: boolean
  lastLoginAt: string | null
  createdAt: string
}

export interface ApiUserUpdateRequest {
  email: string
}

export interface ApiPasswordChangeRequest {
  currentPassword: string
  newPassword: string
}

export interface ApiAuthResponse {
  accessToken: string
  tokenType: string
  user: ApiUserResponse
}

export interface ApiWatchlistItemCreate {
  stockCode: string
  tags?: string[]
  groupId?: number
}

export interface ApiWatchlistItemResponse {
  id: number
  stockCode: string
  tags: string[] | null
  groupId: number
  createdAt: string
}

export interface ApiWatchlistGroupCreate {
  name: string
  aiReviewEnabled?: boolean
}

export interface ApiWatchlistGroupUpdate {
  name?: string
  aiReviewEnabled?: boolean
}

export interface ApiWatchlistGroupResponse {
  id: number
  name: string
  sortOrder: number
  isDefault: boolean
  aiReviewEnabled: boolean
  createdAt: string
}

export interface ApiWatchlistGroupWithItemsResponse extends ApiWatchlistGroupResponse {
  items: ApiWatchlistItemResponse[]
}

export interface ApiWatchlistGroupReorderRequest {
  groupIds: number[]
}

export interface ApiWatchlistItemMoveRequest {
  groupId: number
}

export interface ApiWatchlistScreenshotRecognitionItem {
  stockCode: string
  stockName: string | null
  confidence: number | null
  valid: boolean
  matchedName: string | null
}

export interface ApiWatchlistScreenshotRecognitionResponse {
  items: ApiWatchlistScreenshotRecognitionItem[]
}

export interface ApiWatchlistBatchItemCreate {
  stockCode: string
  tags?: string[]
}

export interface ApiWatchlistBatchCreate {
  items: ApiWatchlistBatchItemCreate[]
  groupId?: number
  newGroupName?: string
}

export interface ApiWatchlistBatchDuplicatedItem {
  stockCode: string
  groupId: number | null
  groupName: string | null
}

export interface ApiWatchlistBatchResponse {
  created: ApiWatchlistItemResponse[]
  duplicated: ApiWatchlistBatchDuplicatedItem[]
  invalid: string[]
}

export interface ApiStockBasicResponse {
  stockCode: string
  stockName: string
  market: string
  fullName: string | null
  industryLevel1: string | null
  industryLevel2: string | null
  industryLevel3: string | null
  listingDate: string | null
  totalShares: number | null
  circulatingShares: number | null
}

export interface ApiStockQuoteResponse {
  code: string
  name: string
  price: number | null
  prevClose: number | null
  change: number | null
  changePct: number | null
  open: number | null
  high: number | null
  low: number | null
  volume: number | null
  amount: number | null
  marketCap: number | null
  circulatingMarketCap: number | null
  updatedAt: string | null
}

export interface ApiStockAiAnalysisSection {
  key: string
  title: string
  content: string
}

export interface ApiStockAiAnalysisResponse {
  stockCode: string
  stockName: string
  tradeDate: string
  model: string | null
  generatedAt: string
  cached: boolean
  sections: ApiStockAiAnalysisSection[]
}

export type ApiStockAiAnalysisStatus = 'running' | 'ready' | 'none'

export interface ApiStockAiAnalysisStatusResponse {
  status: ApiStockAiAnalysisStatus
  data: ApiStockAiAnalysisResponse | null
  tradeDate: string
}

export interface ApiStockAiAnalysisDatesResponse {
  code: string
  tradeDates: string[]
}

export interface ApiStockKlineBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
  changePct: number | null
  amplitude: number | null
  turnoverRate: number | null
}

export interface ApiStockKlineResponse {
  code: string
  name: string
  period: string
  bars: ApiStockKlineBar[]
}

export interface ApiStockIntradayPoint {
  time: string
  price: number
  volume: number
  amount: number
}

export interface ApiStockIntradayResponse {
  code: string
  name: string
  tradeDate: string
  prevClose: number
  points: ApiStockIntradayPoint[]
}

export interface ApiStockSectorItem {
  name: string
  type: 'industry' | 'concept'
  changePct: number | null
  mainNetInflow: number | null
}

export interface ApiStockSectorsResponse {
  code: string
  name: string
  sectors: ApiStockSectorItem[]
}

export interface ApiKlineDataResponse {
  tradeDate: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
  amplitude: number
  changePct: number
  turnoverRate: number
}

export interface ApiAuctionDataResponse {
  tradeDate: string
  matchTime: string
  price: number
  volume: number
  bidPrices: number[]
  bidVolumes: number[]
  askPrices: number[]
  askVolumes: number[]
}

export interface ApiIndexAuctionTrendResponse {
  dates: string[]
  series: Array<{
    code: string
    name: string
    values: Array<number | null>
  }>
}

export interface ApiFundFlowResponse {
  stockCode: string
  tradeDate: string
  mainNetInflow: number
  superLargeNet: number
  largeNet: number
  mediumNet: number
  smallNet: number
}

export interface ApiPaginatedResponse<T> {
  total: number
  page: number
  pageSize: number
  items: T[]
}

export interface ApiChainAnalysisRequest {
  industry: string
  focus?: string | null
}

export interface ApiChainCompany {
  code: string
  name: string
}

export interface ApiChainNode {
  name: string
  type: 'upstream' | 'midstream' | 'downstream'
  description: string
  companies: ApiChainCompany[]
  avgGrossMargin: number | null
  revenueGrowth: number | null
  rdRatio: number | null
  bargainingPower: number | null
  localizationRate: number | null
  techBarrier: string | null
  bottleneckIndicators: string[]
  recentBreakthroughs: string[]
}

export interface ApiChainEdge {
  source: string
  target: string
  relation: string
  strength: number
  description?: string
  criticality: string | null
}

export interface ApiChainOpportunity {
  title: string
  description: string
  relatedSegment: string | null
  confidence: string | null
}

export interface ApiChainRisk {
  title: string
  description: string
  relatedSegment: string | null
  severity: string | null
}

export interface ApiChainValueDistribution {
  highestMarginSegment: string | null
  highestMarginValue: number | null
  lowestMarginSegment: string | null
  lowestMarginValue: number | null
}

export interface ApiKeyCompanySummary {
  code: string
  name: string
  chainPosition: string | null
  score: number | null
}

export interface ApiChainAnalysisResult {
  nodes: ApiChainNode[]
  edges: ApiChainEdge[]
  summary: string
  valueDistribution: ApiChainValueDistribution | null
  opportunities: ApiChainOpportunity[]
  risks: ApiChainRisk[]
  keyCompaniesSummary: ApiKeyCompanySummary[]
}

export interface ApiChainAnalyzeResponse {
  versionId: number
  versionNo: number
  status: string
  result: ApiChainAnalysisResult | null
}

export interface ApiChainVersionSummary {
  id: number
  industry: string
  versionNo: number
  label: string | null
  status: string
  model: string | null
  nodeCount: number | null
  companyCount: number | null
  createdBy: string
  createdAt: string
}

export interface ApiChainVersionDetail {
  version: ApiChainVersionSummary
  result: ApiChainAnalysisResult | null
  errorMsg: string | null
}

export interface ApiChainCompareCompanyChange {
  code: string
  name: string
  nodeName: string
}

export interface ApiChainCompareMetricChange {
  nodeName: string
  field: string
  baseValue: number | null
  targetValue: number | null
}

export interface ApiChainCompareResult {
  baseVersion: ApiChainVersionSummary
  targetVersion: ApiChainVersionSummary
  addedNodes: string[]
  removedNodes: string[]
  addedCompanies: ApiChainCompareCompanyChange[]
  removedCompanies: ApiChainCompareCompanyChange[]
  metricChanges: ApiChainCompareMetricChange[]
}

export interface ApiChainAlert {
  industry: string
  alertType: string
  severity: number
  title: string
  description: string
  affectedSegments: string[]
  relatedStockCodes: string[]
  signalDate: string
  createdAt: string
}

export interface ApiLLMConfigResponse {
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

export interface ApiLLMConfigCreateRequest {
  name: string
  provider: string
  baseUrl: string
  apiKey: string
  modelName: string
  isDefault?: boolean
  isActive?: boolean
  extra?: Record<string, unknown>
}

export interface ApiLLMConfigUpdateRequest {
  name?: string
  provider?: string
  baseUrl?: string
  apiKey?: string
  modelName?: string
  isDefault?: boolean
  isActive?: boolean
  extra?: Record<string, unknown>
}

export interface ApiLLMConfigTestResponse {
  status: string
  detail: string
  testedAt: string
}

export interface ApiCollectorChannelConfigResponse {
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

export interface ApiCollectorChannelConfigCreateRequest {
  source: string
  name: string
  baseUrl?: string
  apiKey?: string
  isEnabled?: boolean
  supportedDataTypes?: string[]
  extra?: Record<string, unknown>
}

export interface ApiCollectorChannelConfigUpdateRequest {
  name?: string
  baseUrl?: string
  apiKey?: string
  isEnabled?: boolean
  supportedDataTypes?: string[]
  extra?: Record<string, unknown>
}

export interface ApiCollectorTaskChannelItem {
  source: string
  name: string
  isEnabled: boolean
}

export interface ApiCollectorTaskChannelsResponse {
  taskName: string
  dataType: string
  channels: ApiCollectorTaskChannelItem[]
  resolvedSource: string | null
}

export interface ApiCollectorTaskRunRequest {
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

export interface ApiCollectorTaskCatalogItem {
  name: string
  label: string
  dataType: string
  sources: string[]
  configParams: string[]
  runParams: string[]
}

export interface ApiCollectorTaskCatalogResponse {
  items: ApiCollectorTaskCatalogItem[]
}

export interface ApiCollectorRunResponse {
  taskName: string
  status: string
  logId?: number | null
  celeryTaskId?: string | null
}

export interface ApiCollectorLogResponse {
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

export interface ApiResearchReportListRequest {
  stock_code?: string | null
  q?: string | null
  start_date?: string | null
  end_date?: string | null
  page?: number
  page_size?: number
}

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

export interface ApiSectorFundFlowResponse {
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

export interface ApiHotspotListRequest {
  sector_type?: string | null
  trade_date?: string | null
  page?: number
  page_size?: number
}

export interface ApiSectorFlowTrendResponse {
  dates: string[]
  sectors: Array<{
    code: string
    name: string
    values: Array<number | null>
  }>
}

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

export interface ApiAdminUserResponse {
  id: number
  username: string
  email: string
  role: string
  isActive: boolean
  lastLoginAt: string | null
  createdAt: string
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

export interface ApiAdminTaskResponse {
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

export interface ApiAdminTaskCreateRequest {
  taskName: string
  taskType: string
  source: string
  schedule?: string
  isActive?: boolean
}

export interface ApiAdminTaskUpdateRequest {
  taskType?: string
  source?: string
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
