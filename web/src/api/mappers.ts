import type {
  ApiAdminNewsResponse,
  ApiAdminReportResponse,
  ApiAdminStockResponse,
  ApiAdminTaskResponse,
  ApiAdminUserResponse,
  ApiAuthResponse,
  ApiBalanceSheetResponse,
  ApiCashFlowStatementResponse,
  ApiChainAnalysisResult,
  ApiChainEdge,
  ApiChainNode,
  ApiCollectorChannelConfigResponse,
  ApiCollectorLogResponse,
  ApiFinancialHealthResponse,
  ApiFundFlowResponse,
  ApiIncomeStatementResponse,
  ApiKlineDataResponse,
  ApiLLMConfigResponse,
  ApiPaginatedResponse,
  ApiResearchReportResponse,
  ApiSectorFundFlowResponse,
  ApiStockBasicResponse,
  ApiUserResponse,
  ApiWatchlistItemResponse,
} from '@ai-invest/shared'
import type {
  AdminNews,
  AdminReport,
  AdminStock,
  AdminTask,
  AdminUser,
  AuthResponse,
  BalanceSheet,
  CashFlowStatement,
  ChainAnalysisResult,
  ChainEdge,
  ChainNode,
  CollectorChannelConfig,
  CollectorLog,
  FinancialHealth,
  FundFlowData,
  IncomeStatement,
  KlineData,
  LLMConfig,
  ResearchReport,
  SectorFundFlow,
  Stock,
  User,
  WatchlistItem,
} from '@ai-invest/shared'

export function mapUser(dto: ApiUserResponse): User {
  return {
    id: String(dto.id),
    username: dto.username,
    email: dto.email,
    isAdmin: dto.role === 'admin',
  }
}

export function mapAuthResponse(dto: ApiAuthResponse): AuthResponse {
  return {
    accessToken: dto.access_token,
    user: mapUser(dto.user),
  }
}

export function mapStock(dto: ApiStockBasicResponse): Stock {
  return {
    code: dto.stock_code,
    name: dto.stock_name,
    industry: dto.industry_l1 || dto.industry_l2 || dto.industry_l3 || '',
    market: normalizeMarket(dto.market),
  }
}

function normalizeMarket(market: string): 'SH' | 'SZ' | 'BJ' {
  const upper = market.toUpperCase()
  if (upper === 'SH' || upper === 'SSE') return 'SH'
  if (upper === 'SZ' || upper === 'SZSE') return 'SZ'
  if (upper === 'BJ' || upper === 'BSE') return 'BJ'
  return 'SH'
}

export function mapKlineData(dto: ApiKlineDataResponse): KlineData {
  return {
    date: dto.trade_date,
    open: Number(dto.open),
    high: Number(dto.high),
    low: Number(dto.low),
    close: Number(dto.close),
    volume: Number(dto.volume),
    amount: Number(dto.amount),
  }
}

export function mapFundFlowData(dto: ApiFundFlowResponse): FundFlowData {
  return {
    code: dto.stock_code,
    date: dto.trade_date,
    mainNetInflow: Number(dto.main_net_inflow),
    superLargeNet: Number(dto.super_large_net),
    largeNet: Number(dto.large_net),
    mediumNet: Number(dto.medium_net),
    smallNet: Number(dto.small_net),
  }
}

export function mapWatchlistItem(dto: ApiWatchlistItemResponse): WatchlistItem {
  return {
    id: String(dto.id),
    code: dto.stock_code,
    tags: dto.tags || [],
    createdAt: dto.created_at,
  }
}

export function mapPaginatedResponse<T, R>(
  dto: ApiPaginatedResponse<T>,
  mapper: (item: T) => R
): { total: number; page: number; pageSize: number; items: R[] } {
  return {
    total: dto.total,
    page: dto.page,
    pageSize: dto.page_size,
    items: dto.items.map(mapper),
  }
}

export function mapChainNode(dto: ApiChainNode): ChainNode {
  return {
    name: dto.name,
    type: dto.type,
    companies: dto.companies,
    avgGrossMargin: Number(dto.avg_gross_margin),
    revenueGrowth: Number(dto.revenue_growth),
    bargainingPower: Number(dto.bargaining_power),
  }
}

export function mapChainEdge(dto: ApiChainEdge): ChainEdge {
  return {
    source: dto.source,
    target: dto.target,
    relation: dto.relation,
    strength: Number(dto.strength),
    description: dto.description || '',
  }
}

export function mapChainAnalysisResult(dto: ApiChainAnalysisResult): ChainAnalysisResult {
  return {
    nodes: dto.nodes.map(mapChainNode),
    edges: dto.edges.map(mapChainEdge),
    summary: dto.summary,
    opportunities: dto.opportunities,
    risks: dto.risks,
  }
}

export function mapLLMConfig(dto: ApiLLMConfigResponse): LLMConfig {
  return {
    id: dto.id,
    name: dto.name,
    provider: dto.provider,
    baseUrl: dto.base_url,
    modelName: dto.model_name,
    apiKeyMasked: dto.api_key_masked,
    isDefault: dto.is_default,
    isActive: dto.is_active,
    extra: dto.extra,
    lastTestedAt: dto.last_tested_at,
    lastTestStatus: dto.last_test_status,
    lastTestError: dto.last_test_error,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapCollectorChannelConfig(dto: ApiCollectorChannelConfigResponse): CollectorChannelConfig {
  return {
    id: dto.id,
    source: dto.source,
    name: dto.name,
    baseUrl: dto.base_url,
    apiKeyMasked: dto.api_key_masked,
    isEnabled: dto.is_enabled,
    supportedDataTypes: dto.supported_data_types,
    extra: dto.extra,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapCollectorLog(dto: ApiCollectorLogResponse): CollectorLog {
  return {
    id: dto.id,
    taskName: dto.task_name,
    source: dto.source,
    status: dto.status,
    startedAt: dto.started_at,
    finishedAt: dto.finished_at,
    recordsCount: dto.records_count,
    errorMsg: dto.error_msg,
    metadata: dto.metadata,
  }
}

export function mapResearchReport(dto: ApiResearchReportResponse): ResearchReport {
  return {
    id: dto.id,
    stockCode: dto.stock_code,
    title: dto.title,
    summary: dto.summary,
    content: dto.content,
    source: dto.source,
    sourceUrl: dto.source_url,
    publishDate: dto.publish_date,
    sentiment: dto.sentiment,
    keywords: dto.keywords,
    industryTags: dto.industry_tags,
    extra: dto.extra,
    createdAt: dto.created_at,
  }
}

export function mapSectorFundFlow(dto: ApiSectorFundFlowResponse): SectorFundFlow {
  return {
    sectorCode: dto.sector_code,
    sectorName: dto.sector_name,
    sectorType: dto.sector_type,
    tradeDate: dto.trade_date,
    mainNetInflow: dto.main_net_inflow,
    superLargeNet: dto.super_large_net,
    largeNet: dto.large_net,
    mediumNet: dto.medium_net,
    smallNet: dto.small_net,
    topStockCode: dto.top_stock_code,
    topStockName: dto.top_stock_name,
    createdAt: dto.created_at,
  }
}

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
    rdExpense: dto.rd_expense,
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
    cfOperations: dto.cf_operations,
    cfInvesting: dto.cf_investing,
    cfFinancing: dto.cf_financing,
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
    balanceSheet: dto.balance_sheet ? mapBalanceSheet(dto.balance_sheet) : null,
    incomeStatement: dto.income_statement
      ? mapIncomeStatement(dto.income_statement)
      : null,
    cashFlowStatement: dto.cash_flow_statement
      ? mapCashFlowStatement(dto.cash_flow_statement)
      : null,
    metrics: dto.metrics,
  }
}

export function mapAdminUser(dto: ApiAdminUserResponse): AdminUser {
  return {
    id: dto.id,
    username: dto.username,
    email: dto.email,
    role: dto.role,
    isActive: dto.is_active,
    lastLoginAt: dto.last_login_at,
    createdAt: dto.created_at,
  }
}

export function mapAdminStock(dto: ApiAdminStockResponse): AdminStock {
  return {
    id: dto.id,
    stockCode: dto.stock_code,
    stockName: dto.stock_name,
    market: dto.market,
    industryL1: dto.industry_l1,
    industryL2: dto.industry_l2,
    industryL3: dto.industry_l3,
    listingDate: dto.listing_date,
    createdAt: dto.created_at,
  }
}

export function mapAdminReport(dto: ApiAdminReportResponse): AdminReport {
  return {
    id: dto.id,
    filePath: dto.file_path,
    originalName: dto.original_name,
    fileType: dto.file_type,
    stockCode: dto.stock_code,
    reportDate: dto.report_date,
    reportType: dto.report_type,
    broker: dto.broker,
    fileSize: dto.file_size,
    md5Hash: dto.md5_hash,
    downloadUrl: dto.download_url,
    downloadCount: dto.download_count,
    uploadedAt: dto.uploaded_at,
  }
}

export function mapAdminNews(dto: ApiAdminNewsResponse): AdminNews {
  return {
    id: dto.id,
    stockCode: dto.stock_code,
    docType: dto.doc_type,
    title: dto.title,
    summary: dto.summary,
    content: dto.content,
    source: dto.source,
    sourceUrl: dto.source_url,
    publishDate: dto.publish_date,
    sentiment: dto.sentiment,
    keywords: dto.keywords,
    industryTags: dto.industry_tags,
    extra: dto.extra,
    createdAt: dto.created_at,
  }
}

export function mapAdminTask(dto: ApiAdminTaskResponse): AdminTask {
  return {
    id: dto.id,
    taskName: dto.task_name,
    taskType: dto.task_type,
    source: dto.source,
    schedule: dto.schedule,
    isActive: dto.is_active,
    lastRunAt: dto.last_run_at,
    lastStatus: dto.last_status,
    lastError: dto.last_error,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}
