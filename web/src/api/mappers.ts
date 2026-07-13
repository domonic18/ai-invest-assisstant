import type {
  ApiAuthResponse,
  ApiChainAnalysisResult,
  ApiChainEdge,
  ApiChainNode,
  ApiCollectorChannelConfigResponse,
  ApiCollectorLogResponse,
  ApiFundFlowResponse,
  ApiKlineDataResponse,
  ApiLLMConfigResponse,
  ApiPaginatedResponse,
  ApiStockBasicResponse,
  ApiUserResponse,
  ApiWatchlistItemResponse,
} from '@ai-invest/shared'
import type {
  AuthResponse,
  ChainAnalysisResult,
  ChainEdge,
  ChainNode,
  CollectorChannelConfig,
  CollectorLog,
  FundFlowData,
  KlineData,
  LLMConfig,
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
