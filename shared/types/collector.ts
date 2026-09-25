/** 采集渠道配置 masked 视图（对应 admin/collector 渠道管理）。 */
export interface ApiCollectorChannelConfigResponse {
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

export interface ApiCollectorChannelConfigCreateRequest {
  source: string
  name: string
  baseUrl?: string
  apiKey?: string
  isEnabled?: boolean
  supportedDataTypes?: string[]
  extra?: Record<string, unknown>
  proxyConfigId?: number | null
}

export interface ApiCollectorChannelConfigUpdateRequest {
  name?: string
  baseUrl?: string
  apiKey?: string
  isEnabled?: boolean
  supportedDataTypes?: string[]
  extra?: Record<string, unknown>
  proxyConfigId?: number | null
}

export interface ApiProxyConfigResponse {
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

export interface ApiProxyConfigCreateRequest {
  name: string
  protocol: 'http' | 'socks5'
  host: string
  port: number
  username?: string
  password?: string
  isEnabled?: boolean
}

/** password 留空/缺省表示不修改已存储的密码。 */
export interface ApiProxyConfigUpdateRequest {
  name?: string
  protocol?: 'http' | 'socks5'
  host?: string
  port?: number
  username?: string | null
  password?: string
  isEnabled?: boolean
}

export interface ApiProxyConfigTestResponse {
  ok: boolean
  statusCode: number | null
  latencyMs: number
  error: string | null
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
  description: string
  dataType: string
  sources: string[]
  configParams: string[]
  runParams: string[]
  defaults?: Record<string, unknown> | null
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
  message?: string | null
  metadata: Record<string, unknown> | null
}

export interface ApiCollectorLogSummaryResponse {
  date: string
  successCount: number
  partialCount: number
  failedCount: number
  skippedCount: number
  runningCount: number
  pendingCount: number
}

// ---------------------------------------------------------------------------
// 采集健康监测（F-MON 一期）
// ---------------------------------------------------------------------------

export type CollectorHealthStatus =
  | 'healthy'
  | 'degraded'
  | 'critical'
  | 'silent'
  | 'paused'
  | 'unconfigured'

export type CollectorHealthRole = 'primary' | 'backup' | 'single'

export type CollectorErrorCause =
  | 'waf'
  | 'network'
  | 'parse'
  | 'auth'
  | 'timeout'
  | 'not_ready'
  | 'other'

export interface ApiCollectorHealthCounts {
  healthy: number
  degraded: number
  critical: number
  silent: number
  paused: number
  unconfigured: number
}

export interface ApiCollectorHealthDomainSummary {
  domain: string
  total: number
  healthy: number
  degraded: number
  critical: number
  silent: number
}

export interface ApiCollectorHealthOverview {
  healthScore: number
  total: number
  counts: ApiCollectorHealthCounts
  successRate24h: number | null
  domains: ApiCollectorHealthDomainSummary[]
  checkedAt: string | null
  staleAfter: string | null
}

export interface ApiCollectorHealthTaskItem {
  taskType: string
  source: string
  status: CollectorHealthStatus
  role: CollectorHealthRole
  domain: string
  successRate24h: number | null
  successRate7d: number | null
  consecutiveFailures: number
  windowsWithoutSuccess: number
  lastSuccessAt: string | null
  lastErrorSummary: string | null
  lastErrorCause: CollectorErrorCause | null
  /** 判定依据（why，按序）——解释该状态如何得出 */
  reasons: string[]
  isHighFrequency: boolean
  lastRecordsCount: number | null
  lastRecordsDate: string | null
  stateChangedAt: string
  checkedAt: string
  schedule: string | null
  isActive: boolean | null
}

export interface ApiCollectorChannelHealthItem {
  source: string
  domainCount: number
  instanceCount: number
  successRate7d: number | null
  faultCount: number
  causes: Record<string, number>
}

export interface ApiCollectorScheduleCheckItem {
  taskType: string
  source: string
  domain: string
  role: CollectorHealthRole
  isActive: boolean
  hasTaskRow: boolean
  schedule: string | null
  windowTotal: number
  successWindows: number
  skippedWindows: number
  failedWindows: number
  missingWindows: number
  exempted: boolean
  lastErrorSummary: string | null
  lastErrorCause: CollectorErrorCause | null
}

export interface ApiCollectorScheduleCheckResponse {
  date: string
  isTradeDay: boolean
  items: ApiCollectorScheduleCheckItem[]
}

export interface ApiCollectorRunHealthCheckResponse {
  checkedAt: string
  total: number
  failed: number
  orphaned: number
  statusCounts: Record<string, number>
}

export interface ApiCollectorClearSnapshotsResponse {
  deleted: number
}
