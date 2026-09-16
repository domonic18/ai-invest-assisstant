/** 社媒大 V 情绪（F-SOC）：用户侧情绪流/账号卡/时间线 + 管理端账号与 ASR 配置类型，camelCase wire。 */

export type ApiSocialStance = 'bullish' | 'bearish' | 'neutral'

export type ApiSocialTargetType = 'index' | 'sector' | 'stock' | 'commodity'

/** 影响标的（情绪流卡片 chips）。 */
export interface ApiSocialTarget {
  targetType: ApiSocialTargetType
  name: string
  code: string | null
}

/** 情绪流卡片（GET /social/sentiment-feed 列表项）。 */
export interface ApiSocialFeedItem {
  postId: number
  videoId: string
  platform: string
  accountId: number
  accountAlias: string
  category: string
  title: string | null
  caption: string | null
  topicTags: string[]
  coverUrl: string | null
  durationSeconds: number | null
  /** ISO 时间（前端跨日分组键） */
  publishedAt: string
  diggCount: number | null
  commentCount: number | null
  shareCount: number | null
  /** 音频转写降级（true=判断仅基于标题/文案） */
  transcriptMissing: boolean
  isRelevant: boolean
  stance: ApiSocialStance
  confidence: number
  coreArguments: string[]
  targets: ApiSocialTarget[]
  summary: string
}

/** GET /social/sentiment-feed 分页响应。 */
export interface ApiSocialFeedPage {
  total: number
  page: number
  pageSize: number
  items: ApiSocialFeedItem[]
}

/** 账号维度卡（GET /social/accounts 列表项，近 7 日多空分布）。 */
export interface ApiSocialAccountCard {
  id: number
  alias: string
  category: string
  lastPostAt: string | null
  latestStance: ApiSocialStance | null
  latestConfidence: number | null
  latestSummary: string | null
  latestCoverUrl: string | null
  bullishCount7d: number
  bearishCount7d: number
  neutralCount7d: number
}

/** GET /social/accounts 响应。 */
export interface ApiSocialAccountsResponse {
  accounts: ApiSocialAccountCard[]
}

/** 单账号时间线项（GET /social/accounts/{id}/timeline）。 */
export interface ApiSocialTimelineItem {
  postId: number
  videoId: string
  title: string | null
  publishedAt: string
  stance: ApiSocialStance
  confidence: number
  summary: string
  transcriptMissing: boolean
}

/** GET /social/accounts/{id}/timeline 分页响应。 */
export interface ApiSocialTimelinePage {
  total: number
  page: number
  pageSize: number
  items: ApiSocialTimelineItem[]
}

// ============ 管理端（/admin/social/*） ============

/** 追踪账号行（管理端清单，含诊断列）。 */
export interface ApiSocialAccountAdmin {
  id: number
  platform: string
  secUid: string
  alias: string
  category: string
  pollIntervalMinutes: number
  isActive: boolean
  remark: string | null
  lastCollectedAt: string | null
  lastPostAt: string | null
  lastError: string | null
  lastErrorAt: string | null
  createdAt: string
}

export interface ApiSocialAccountsAdminPage {
  total: number
  page: number
  pageSize: number
  items: ApiSocialAccountAdmin[]
}

/** 登记追踪账号（secUidOrUrl 支持裸 sec_uid / 主页链接 / 分享短链）。 */
export interface ApiSocialAccountCreateRequest {
  platform?: string
  secUidOrUrl: string
  alias: string
  category?: string
  pollIntervalMinutes?: number
  remark?: string | null
}

export interface ApiSocialAccountUpdateRequest {
  alias?: string
  category?: string
  pollIntervalMinutes?: number
  isActive?: boolean
  remark?: string | null
}

/** 触发历史视频回填采集（POST /admin/social/accounts/{id}/backfill 响应）。 */
export interface ApiSocialBackfillResponse {
  logId: number
  celeryTaskId: string | null
}

/** 作品级排查行（GET /admin/social/accounts/{id}/posts）。 */
export interface ApiSocialPostDebug {
  videoId: string
  title: string | null
  publishedAt: string
  transcriptStatus: string
  transcriptReason: string | null
  judgedAt: string | null
  /** null = 未判；false = 已判不入流 */
  isRelevant: boolean | null
  stance: string | null
  confidence: number | null
}

/** 抖音适配层健康（GET /admin/social/status douyin 字段）。 */
export interface ApiDouyinStatus {
  cookieConfigured: boolean
  cookieJarsAvailable: number
  lastBootstrapAt: string | null
  /** 最近失败日志含签名错误（a_bogus 跟版信号） */
  signatureWarning: boolean
  todayCollected: number
  todayFailed: number
}

/** ASR 转写状态（GET /admin/social/status asr 字段）。 */
export interface ApiAsrStatus {
  enabled: boolean
  configured: boolean
  todayTranscribed: number
  todayDegraded: number
}

/** 签名 sidecar 状态（GET /admin/social/status signer 字段）。 */
export interface ApiSignerStatus {
  enabled: boolean
  reachable: boolean
  warmSlots: number | null
  detail: string | null
}

export interface ApiSocialStatus {
  douyin: ApiDouyinStatus
  asr: ApiAsrStatus
  signer: ApiSignerStatus
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

/** 手动导入抖音 Cookie（ttwid 必需）。 */
export interface ApiSocialCookieImportRequest {
  cookie: string
}

export interface ApiSocialCookieImportResponse {
  cookieJarsAvailable: number
}
