import type {
  ApiAdminNewsResponse,
  ApiAdminReportResponse,
  ApiAdminStockResponse,
  ApiAdminTaskResponse,
  ApiAdminUserResponse,
  ApiAuctionDataResponse,
  ApiAuthResponse,
  ApiBalanceSheetResponse,
  ApiCashFlowStatementResponse,
  ApiChainAnalysisResult,
  ApiChainCompareResult,
  ApiChainEdge,
  ApiChainNode,
  ApiChainVersionDetail,
  ApiChainVersionSummary,
  ApiCollectorChannelConfigResponse,
  ApiDataTypeChannelsResponse,
  ApiCollectorLogResponse,
  ApiFinancialHealthResponse,
  ApiIncomeStatementResponse,
  ApiKlineDataResponse,
  ApiLLMConfigResponse,
  ApiPaginatedResponse,
  ApiResearchReportResponse,
  ApiSectorFundFlowResponse,
  ApiStockBasicResponse,
  ApiUserResponse,
  ApiUserSettings,
  ApiWatchlistItemResponse,
} from '@ai-invest/shared'
import type {
  AdminNews,
  AdminReport,
  AdminStock,
  AdminTask,
  AdminUser,
  AuctionData,
  AuthResponse,
  BalanceSheet,
  CashFlowStatement,
  ChainAnalysisResult,
  ChainCompareResult,
  ChainEdge,
  ChainNode,
  ChainVersionDetail,
  ChainVersionSummary,
  CollectorChannelConfig,
  CollectorDataTypeChannels,
  CollectorLog,
  FinancialHealth,
  IncomeStatement,
  KlineData,
  LLMConfig,
  MovingAverageConfig,
  ResearchReport,
  SectorFundFlow,
  Stock,
  User,
  UserSettings,
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

export function mapUserSettings(dto: ApiUserSettings): UserSettings {
  return {
    maConfigs: dto.ma_configs.map(
      (item): MovingAverageConfig => ({
        period: item.period,
        color: item.color,
        enabled: item.enabled,
      })
    ),
  }
}

export function mapStock(dto: ApiStockBasicResponse): Stock {
  return {
    code: dto.stock_code,
    name: dto.stock_name,
    industry: dto.industry_level_1 || dto.industry_level_2 || dto.industry_level_3 || '',
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

export function mapAuctionData(dto: ApiAuctionDataResponse): AuctionData {
  return {
    date: dto.trade_date,
    time: dto.match_time,
    price: Number(dto.price),
    volume: Number(dto.volume),
    bidPrices: dto.bid_prices,
    bidVolumes: dto.bid_volumes,
    askPrices: dto.ask_prices,
    askVolumes: dto.ask_volumes,
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
    description: dto.description || '',
    companies: dto.companies,
    avgGrossMargin: dto.avg_gross_margin,
    revenueGrowth: dto.revenue_growth,
    rdRatio: dto.rd_ratio,
    bargainingPower: dto.bargaining_power,
    localizationRate: dto.localization_rate,
    techBarrier: dto.tech_barrier,
    bottleneckIndicators: dto.bottleneck_indicators || [],
    recentBreakthroughs: dto.recent_breakthroughs || [],
  }
}

export function mapChainEdge(dto: ApiChainEdge): ChainEdge {
  return {
    source: dto.source,
    target: dto.target,
    relation: dto.relation,
    strength: Number(dto.strength),
    description: dto.description || '',
    criticality: dto.criticality,
  }
}

export function mapChainAnalysisResult(dto: ApiChainAnalysisResult): ChainAnalysisResult {
  return {
    nodes: dto.nodes.map(mapChainNode),
    edges: dto.edges.map(mapChainEdge),
    summary: dto.summary,
    valueDistribution: dto.value_distribution
      ? {
          highestMarginSegment: dto.value_distribution.highest_margin_segment,
          highestMarginValue: dto.value_distribution.highest_margin_value,
          lowestMarginSegment: dto.value_distribution.lowest_margin_segment,
          lowestMarginValue: dto.value_distribution.lowest_margin_value,
        }
      : null,
    opportunities: dto.opportunities.map((item) => ({
      title: item.title,
      description: item.description || '',
      relatedSegment: item.related_segment,
      confidence: item.confidence,
    })),
    risks: dto.risks.map((item) => ({
      title: item.title,
      description: item.description || '',
      relatedSegment: item.related_segment,
      severity: item.severity,
    })),
    keyCompaniesSummary: (dto.key_companies_summary || []).map((item) => ({
      code: item.code,
      name: item.name,
      chainPosition: item.chain_position,
      score: item.score,
    })),
  }
}

export function mapChainVersionSummary(dto: ApiChainVersionSummary): ChainVersionSummary {
  return {
    id: dto.id,
    industry: dto.industry_level_1,
    versionNo: dto.version_no,
    label: dto.label,
    status: dto.status,
    model: dto.model,
    nodeCount: dto.node_count,
    companyCount: dto.company_count,
    createdBy: dto.created_by,
    createdAt: dto.created_at,
  }
}

export function mapChainVersionDetail(dto: ApiChainVersionDetail): ChainVersionDetail {
  return {
    version: mapChainVersionSummary(dto.version),
    result: dto.result ? mapChainAnalysisResult(dto.result) : null,
    errorMsg: dto.error_msg,
  }
}

export function mapChainCompareResult(dto: ApiChainCompareResult): ChainCompareResult {
  return {
    baseVersion: mapChainVersionSummary(dto.base_version),
    targetVersion: mapChainVersionSummary(dto.target_version),
    addedNodes: dto.added_nodes,
    removedNodes: dto.removed_nodes,
    addedCompanies: dto.added_companies.map((item) => ({
      code: item.code,
      name: item.name,
      nodeName: item.node_name,
    })),
    removedCompanies: dto.removed_companies.map((item) => ({
      code: item.code,
      name: item.name,
      nodeName: item.node_name,
    })),
    metricChanges: dto.metric_changes.map((item) => ({
      nodeName: item.node_name,
      field: item.field,
      baseValue: item.base_value,
      targetValue: item.target_value,
    })),
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
    broker: dto.broker,
    rating: dto.rating,
    pages: dto.pages,
    industry: dto.industry,
    hasSummary: dto.has_summary,
  }
}

export function mapSectorFundFlow(dto: ApiSectorFundFlowResponse): SectorFundFlow {
  return {
    sectorCode: dto.sector_code,
    sectorName: dto.sector_name,
    sectorType: dto.sector_type,
    tradeDate: dto.trade_date,
    changePct: dto.change_pct,
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
    industryL1: dto.industry_level_1,
    industryL2: dto.industry_level_2,
    industryL3: dto.industry_level_3,
    listingDate: dto.listing_date,
    totalShares: dto.total_shares,
    circulatingShares: dto.circulating_shares,
    fullName: dto.full_name,
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
    stockName: dto.stock_name,
    reportDate: dto.report_date,
    reportType: dto.report_type,
    broker: dto.broker,
    fileSize: dto.file_size,
    md5Hash: dto.md5_hash,
    downloadUrl: dto.download_url,
    downloadCount: dto.download_count,
    createdAt: dto.created_at,
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

export function mapCollectorDataTypeChannels(dto: ApiDataTypeChannelsResponse): CollectorDataTypeChannels {
  return {
    dataType: dto.data_type,
    channels: dto.channels.map((ch) => ({
      channelId: ch.channel_id,
      source: ch.source,
      name: ch.name,
      isEnabled: ch.is_enabled,
      priority: ch.priority,
    })),
  }
}
