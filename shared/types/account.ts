// 账号准入与 AI 用量治理域契约（F-ACCT，arch/10）
// wire（Api*）与前端域模型同文件维护；wire 字段 camelCase

// ---- 账号状态 ----

export type AccountStatus = 'pending' | 'approved' | 'rejected'
export type UsageFeature =
  | 'assistant'
  | 'page'
  | 'api_key'
  | 'system'
  | 'kb_clean'
  | 'kb_extract'
  | 'kb_vision'
  | 'kb_embed'
  | 'kb_optimize'
export type UsageOutlet = 'system' | 'byok'

// ---- 个人侧（wire） ----

export interface ApiQuotaResponse {
  totalTokens: number | null
  usedTokens: number
  remainingTokens: number | null
  unlimited: boolean
  byokEnabled: boolean
}

export interface ApiUsageItem {
  feature: UsageFeature
  modelName: string
  outlet: UsageOutlet
  promptTokens: number
  completionTokens: number
  totalTokens: number
  estimated: boolean
  createdAt: string
}

export interface ApiUsageResponse {
  items: ApiUsageItem[]
  byFeature: Record<string, number>
}

export interface ApiUserLlmConfigResponse {
  protocol: 'openai' | 'anthropic'
  baseUrl: string
  modelName: string
  apiKeyMasked: string
}

export interface ApiUserLlmConfigUpsertRequest {
  protocol: 'openai' | 'anthropic'
  baseUrl: string
  modelName: string
  apiKey: string
}

export interface ApiLlmConnectionTestResponse {
  status: 'success' | 'failed'
  detail: string
}

export interface ApiRegisterAcceptedResponse {
  message: string
}

// ---- 管理侧（wire） ----

export interface ApiPendingApplication {
  id: number
  username: string
  email: string
  applicationNote: string | null
  createdAt: string
}

export interface ApiApproveRequest {
  initialQuotaTokens?: number | null
}

export interface ApiRejectRequest {
  reason: string
}

export interface ApiQuotaAdjustRequest {
  action: 'adjust' | 'reset'
  deltaTokens?: number | null
}

export interface ApiUsageTrendPoint {
  date: string
  totalTokens: number
}

export interface ApiUsageTopUser {
  userId: number | null
  username: string | null
  totalTokens: number
}

export interface ApiUsageDashboardResponse {
  days: number
  trendDaily: ApiUsageTrendPoint[]
  byFeature: Record<string, number>
  byModel: Record<string, number>
  topUsers: ApiUsageTopUser[]
  estimatedRatio: number
  exhaustedUsers: number
}

export interface ApiUsagePerUserDailyPoint {
  date: string
  totalTokens: number
}

export interface ApiUsagePerUser {
  userId: number
  username: string | null
  totalTokens: number
  calls: number
  lastUsedAt: string | null
  daily: ApiUsagePerUserDailyPoint[]
}

export interface ApiAccountSettings {
  defaultQuotaTokens: number
  pendingExpireDays: number
  adminExempt: boolean
}

export interface ApiAccountSettingsUpdateRequest {
  defaultQuotaTokens?: number
  pendingExpireDays?: number
  adminExempt?: boolean
}

// ---- 前端域模型 ----

export interface QuotaInfo {
  totalTokens: number | null
  usedTokens: number
  remainingTokens: number | null
  unlimited: boolean
  byokEnabled: boolean
}

export interface UsageRecord {
  feature: UsageFeature
  modelName: string
  outlet: UsageOutlet
  promptTokens: number
  completionTokens: number
  totalTokens: number
  estimated: boolean
  createdAt: string
}

export interface UsageSummary {
  items: UsageRecord[]
  byFeature: Record<string, number>
}

export interface UserLlmConfig {
  protocol: 'openai' | 'anthropic'
  baseUrl: string
  modelName: string
  apiKeyMasked: string
}

export interface LlmConnectionTestResult {
  status: 'success' | 'failed'
  detail: string
}

export interface PendingApplication {
  id: number
  username: string
  email: string
  applicationNote: string | null
  createdAt: string
}

export interface UsageDashboard {
  days: number
  trendDaily: ApiUsageTrendPoint[]
  byFeature: Record<string, number>
  byModel: Record<string, number>
  topUsers: ApiUsageTopUser[]
  estimatedRatio: number
  exhaustedUsers: number
}

export const USAGE_FEATURE_LABELS: Record<UsageFeature, string> = {
  assistant: '助手对话',
  page: '页面生成',
  api_key: 'API-KEY/MCP',
  system: '系统任务',
  kb_clean: '知识库清洗',
  kb_extract: '知识库抽取',
  kb_vision: '知识库视觉',
  kb_embed: '知识库嵌入',
  kb_optimize: '技能优化',
}

export const ACCOUNT_STATUS_LABELS: Record<AccountStatus, string> = {
  pending: '待审批',
  approved: '正常',
  rejected: '已驳回',
}
