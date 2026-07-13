export interface ApiRegisterRequest {
  username: string
  email: string
  password: string
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
}

export interface ApiWatchlistItemResponse {
  id: number
  stock_code: string
  tags: string[] | null
  created_at: string
}

export interface ApiStockBasicResponse {
  stock_code: string
  stock_name: string
  market: string
  industry_l1: string | null
  industry_l2: string | null
  industry_l3: string | null
  listing_date: string | null
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
  pct_change: number
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
  companies: ApiChainCompany[]
  avg_gross_margin: number
  revenue_growth: number
  bargaining_power: number
}

export interface ApiChainEdge {
  source: string
  target: string
  relation: string
  strength: number
  description?: string
}

export interface ApiChainAnalysisResult {
  nodes: ApiChainNode[]
  edges: ApiChainEdge[]
  summary: string
  opportunities: string[]
  risks: string[]
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
