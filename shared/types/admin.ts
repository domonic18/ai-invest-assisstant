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
  | 'auction'
  | 'fund-flow'
  | 'news'
  | 'company-profile'
  | 'disclosure'
  | 'sector-fund-flow'
  | 'dragon-list'
  | 'research-report'
  | 'macro'

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
