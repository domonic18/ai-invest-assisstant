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
  ma_configs: ApiMovingAverageConfig[]
}

export interface ApiUserSettingsUpdateRequest {
  ma_configs: ApiMovingAverageConfig[]
}

export interface ApiUserResponse {
  id: number
  username: string
  email: string
  role: string
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

export interface ApiAuthResponse {
  access_token: string
  token_type: string
  user: ApiUserResponse
}

export interface ApiWatchlistItemCreate {
  stock_code: string
  tags?: string[]
  group_id?: number
}

export interface ApiWatchlistItemResponse {
  id: number
  stock_code: string
  tags: string[] | null
  group_id: number
  created_at: string
}

export interface ApiWatchlistGroupCreate {
  name: string
  ai_review_enabled?: boolean
}

export interface ApiWatchlistGroupUpdate {
  name?: string
  ai_review_enabled?: boolean
}

export interface ApiWatchlistGroupResponse {
  id: number
  name: string
  sort_order: number
  is_default: boolean
  ai_review_enabled: boolean
  created_at: string
}

export interface ApiWatchlistGroupWithItemsResponse extends ApiWatchlistGroupResponse {
  items: ApiWatchlistItemResponse[]
}

export interface ApiWatchlistGroupReorderRequest {
  group_ids: number[]
}

export interface ApiWatchlistItemMoveRequest {
  group_id: number
}

export interface ApiStockBasicResponse {
  stock_code: string
  stock_name: string
  market: string
  industry_level_1: string | null
  industry_level_2: string | null
  industry_level_3: string | null
  listing_date: string | null
  total_shares: number | null
  circulating_shares: number | null
}

export interface ApiStockQuoteResponse {
  code: string
  name: string
  price: number | null
  prev_close: number | null
  change: number | null
  change_pct: number | null
  open: number | null
  high: number | null
  low: number | null
  volume: number | null
  amount: number | null
  market_cap: number | null
  circulating_market_cap: number | null
  updated_at: string | null
}

export interface ApiStockAiAnalysisSection {
  key: string
  title: string
  content: string
}

export interface ApiStockAiAnalysisResponse {
  stock_code: string
  stock_name: string
  trade_date: string
  model: string | null
  generated_at: string
  cached: boolean
  sections: ApiStockAiAnalysisSection[]
}

export interface ApiStockKlineBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
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
  trade_date: string
  prev_close: number
  points: ApiStockIntradayPoint[]
}

export interface ApiStockSectorItem {
  name: string
  type: 'industry' | 'concept'
  change_pct: number | null
  main_net_inflow: number | null
}

export interface ApiStockSectorsResponse {
  code: string
  name: string
  sectors: ApiStockSectorItem[]
}

export interface ApiKlineDataResponse {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
  amplitude: number
  change_pct: number
  turnover_rate: number
}

export interface ApiAuctionDataResponse {
  trade_date: string
  match_time: string
  price: number
  volume: number
  bid_prices: number[]
  bid_volumes: number[]
  ask_prices: number[]
  ask_volumes: number[]
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
  stock_code: string
  trade_date: string
  main_net_inflow: number
  super_large_net: number
  large_net: number
  medium_net: number
  small_net: number
}

export interface ApiPaginatedResponse<T> {
  total: number
  page: number
  page_size: number
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
  base_url: string
  model_name: string
  api_key_masked: string
  is_default: boolean
  is_active: boolean
  extra: Record<string, unknown>
  last_tested_at: string | null
  last_test_status: string | null
  last_test_error: string | null
  created_at: string
  updated_at: string
}

export interface ApiLLMConfigCreateRequest {
  name: string
  provider: string
  base_url: string
  api_key: string
  model_name: string
  is_default?: boolean
  is_active?: boolean
  extra?: Record<string, unknown>
}

export interface ApiLLMConfigUpdateRequest {
  name?: string
  provider?: string
  base_url?: string
  api_key?: string
  model_name?: string
  is_default?: boolean
  is_active?: boolean
  extra?: Record<string, unknown>
}

export interface ApiLLMConfigTestResponse {
  status: string
  detail: string
  tested_at: string
}

export interface ApiCollectorChannelConfigResponse {
  id: number
  source: string
  name: string
  base_url: string | null
  api_key_masked: string | null
  is_enabled: boolean
  supported_data_types: string[]
  extra: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ApiCollectorChannelConfigCreateRequest {
  source: string
  name: string
  base_url?: string
  api_key?: string
  is_enabled?: boolean
  supported_data_types?: string[]
  extra?: Record<string, unknown>
}

export interface ApiCollectorChannelConfigUpdateRequest {
  name?: string
  base_url?: string
  api_key?: string
  is_enabled?: boolean
  supported_data_types?: string[]
  extra?: Record<string, unknown>
}

export interface ApiCollectorTaskChannelItem {
  source: string
  name: string
  is_enabled: boolean
}

export interface ApiCollectorTaskChannelsResponse {
  task_name: string
  data_type: string
  channels: ApiCollectorTaskChannelItem[]
  resolved_source: string | null
}

export interface ApiCollectorTaskRunRequest {
  preferred_source?: string | null
  symbols?: string[] | null
  period?: string | null
  start_date?: string | null
  end_date?: string | null
  sector_type?: string | null
  indicators?: string[] | null
  report_types?: string[] | null
  report_date?: string | null
  trade_date?: string | null
}

export interface ApiCollectorTaskCatalogItem {
  name: string
  label: string
  data_type: string
  sources: string[]
  config_params: string[]
  run_params: string[]
}

export interface ApiCollectorTaskCatalogResponse {
  items: ApiCollectorTaskCatalogItem[]
}

export interface ApiCollectorRunResponse {
  task_name: string
  status: string
}

export interface ApiCollectorLogResponse {
  id: number
  task_name: string
  source: string | null
  status: string
  started_at: string | null
  finished_at: string | null
  records_count: number
  error_msg: string | null
  metadata: Record<string, unknown> | null
}

export interface ApiResearchReportResponse {
  id: number
  stock_code: string | null
  title: string
  summary: string | null
  content: string | null
  source: string | null
  source_url: string | null
  publish_date: string | null
  sentiment: number | null
  keywords: string[] | null
  industry_tags: string[] | null
  extra: Record<string, unknown>
  created_at: string
  broker: string | null
  rating: string | null
  pages: number | null
  industry: string | null
  has_summary: boolean
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
  stock_code: string | null
  stock_name: string | null
  title: string | null
  report_type: string | null
  report_date: string | null
  file_size: number | null
  summary: string | null
  has_summary: boolean
  created_at: string
}

export interface ApiFinancialSummarizeResponse {
  summary: string
  cached: boolean
}

export interface ApiFinancialReportCollectRequest {
  stock_code: string
  report_types?: string[] | null
  start_date?: string | null
  end_date?: string | null
}

export interface ApiFinancialReportCollectResponse {
  log_id: number
  status: string
}

export interface ApiFinancialReportCollectLogResponse {
  log_id: number
  status: string
  records_count: number
  error_msg: string | null
  finished_at: string | null
}

export interface ApiSectorFundFlowResponse {
  sector_code: string
  sector_name: string
  sector_type: string
  trade_date: string
  change_pct: number | null
  main_net_inflow: number | null
  super_large_net: number | null
  large_net: number | null
  medium_net: number | null
  small_net: number | null
  top_stock_code: string | null
  top_stock_name: string | null
  created_at: string
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
  stock_code: string
  report_date: string
  report_type: string
  total_assets: number | null
  current_assets: number | null
  cash_equivalents: number | null
  accounts_receivable: number | null
  inventory: number | null
  fixed_assets: number | null
  intangible_assets: number | null
  goodwill: number | null
  total_liabilities: number | null
  current_liabilities: number | null
  long_term_debt: number | null
  total_equity: number | null
  paid_in_capital: number | null
  retained_earnings: number | null
  created_at: string
}

export interface ApiIncomeStatementResponse {
  stock_code: string
  report_date: string
  report_type: string
  total_revenue: number | null
  operating_cost: number | null
  selling_expense: number | null
  admin_expense: number | null
  research_development_expense: number | null
  finance_expense: number | null
  operating_profit: number | null
  net_profit: number | null
  net_profit_deducted: number | null
  eps: number | null
  created_at: string
}

export interface ApiCashFlowStatementResponse {
  stock_code: string
  report_date: string
  report_type: string
  cash_flow_from_operations: number | null
  cash_flow_from_investing: number | null
  cash_flow_from_financing: number | null
  net_cash_flow: number | null
  free_cash_flow: number | null
  created_at: string
}

export interface ApiFinancialHealthResponse {
  stock_code: string
  report_date: string | null
  report_type: string | null
  financial_balance_sheet: ApiBalanceSheetResponse | null
  financial_income_statement: ApiIncomeStatementResponse | null
  financial_cash_flow_statement: ApiCashFlowStatementResponse | null
  metrics: Record<string, number | null>
}

export interface ApiFinancialHistoryResponse {
  stock_code: string
  history: ApiFinancialHealthResponse[]
}

export interface ApiAdminUserResponse {
  id: number
  username: string
  email: string
  role: string
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

export interface ApiAdminUserCreateRequest {
  username: string
  email: string
  password: string
  role?: string
  is_active?: boolean
}

export interface ApiAdminUserUpdateRequest {
  username?: string
  email?: string
  role?: string
  is_active?: boolean
}

export interface ApiAdminUserResetPasswordRequest {
  password: string
}

export interface ApiAdminStockResponse {
  id: number
  stock_code: string
  stock_name: string
  market: string
  industry_level_1: string | null
  industry_level_2: string | null
  industry_level_3: string | null
  listing_date: string | null
  total_shares: number | null
  circulating_shares: number | null
  full_name: string | null
  created_at: string
}

export interface ApiAdminStockCreateRequest {
  stock_code: string
  stock_name: string
  market: string
  industry_level_1?: string
  industry_level_2?: string
  industry_level_3?: string
  listing_date?: string
}

export interface ApiAdminStockUpdateRequest {
  stock_name?: string
  market?: string
  industry_level_1?: string
  industry_level_2?: string
  industry_level_3?: string
  listing_date?: string
}

export interface ApiAdminReportResponse {
  id: number
  file_path: string
  original_name: string | null
  file_type: string
  stock_code: string | null
  stock_name: string | null
  report_date: string | null
  report_type: string | null
  broker: string | null
  file_size: number | null
  md5_hash: string | null
  download_url: string | null
  download_count: number
  created_at: string
}

export interface ApiAdminReportCreateRequest {
  file_path: string
  original_name?: string
  file_type: string
  stock_code?: string
  report_date?: string
  report_type?: string
  broker?: string
  file_size?: number
  md5_hash?: string
  download_url?: string
}

export interface ApiAdminReportUpdateRequest {
  original_name?: string
  file_type?: string
  stock_code?: string
  report_date?: string
  report_type?: string
  broker?: string
  file_size?: number
  md5_hash?: string
  download_url?: string
}

export interface ApiAdminNewsResponse {
  id: number
  stock_code: string | null
  doc_type: string
  title: string
  summary: string | null
  content: string | null
  source: string | null
  source_url: string | null
  publish_date: string | null
  sentiment: number | null
  keywords: string[] | null
  industry_tags: string[] | null
  extra: Record<string, unknown>
  created_at: string
}

export interface ApiAdminNewsCreateRequest {
  stock_code?: string
  doc_type: string
  title: string
  summary?: string
  content?: string
  source?: string
  source_url?: string
  publish_date?: string
  sentiment?: number
  keywords?: string[]
  industry_tags?: string[]
  extra?: Record<string, unknown>
}

export interface ApiAdminNewsUpdateRequest {
  stock_code?: string
  doc_type?: string
  title?: string
  summary?: string
  content?: string
  source?: string
  source_url?: string
  publish_date?: string
  sentiment?: number
  keywords?: string[]
  industry_tags?: string[]
  extra?: Record<string, unknown>
}

export interface ApiAdminTaskResponse {
  id: number
  task_name: string
  task_type: string
  source: string
  schedule: string | null
  is_active: boolean
  last_run_at: string | null
  last_status: string
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface ApiAdminTaskCreateRequest {
  task_name: string
  task_type: string
  source: string
  schedule?: string
  is_active?: boolean
}

export interface ApiAdminTaskUpdateRequest {
  task_type?: string
  source?: string
  schedule?: string
  is_active?: boolean
}

export interface ApiDataTypeChannelItem {
  channel_id: number
  source: string
  name: string
  is_enabled: boolean
  priority: number
}

export interface ApiDataTypeChannelsResponse {
  data_type: string
  channels: ApiDataTypeChannelItem[]
}

export interface ApiDataTypeChannelPriorityInput {
  channel_id: number
  priority: number
}

export interface ApiTrackedIndexResponse {
  id: number
  index_code: string
  index_name: string
  market_category: string
  data_source: string
  sort_order: number
  is_enabled: boolean
  latest_close: number | null
  latest_change_pct: number | null
  latest_trade_date: string | null
  created_at: string
  updated_at: string
}

export interface ApiTrackedIndexCreateRequest {
  index_code: string
  index_name: string
  market_category: string
  data_source: string
  sort_order?: number
  is_enabled?: boolean
}

export interface ApiTrackedIndexUpdateRequest {
  index_name?: string
  market_category?: string
  data_source?: string
  sort_order?: number
  is_enabled?: boolean
}

export interface ApiTrackedIndexToggleResponse {
  id: number
  is_enabled: boolean
}
