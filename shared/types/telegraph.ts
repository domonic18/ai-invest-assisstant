/** 财联社电报（news_telegraph）类型：camelCase wire + camelCase 领域类型。 */

/** 后端 GET /telegraph 分页响应。 */
export interface ApiTelegraphPage {
  total: number
  page: number
  pageSize: number
  items: ApiTelegraphResponse[]
}

/** 后端电报条目。 */
export interface ApiTelegraphResponse {
  clsMsgId: number
  title: string | null
  content: string | null
  category: string | null
  importance: number | null
  shared: number | null
  stockCodes: string[] | null
  publishTime: string
  /** AI 重要度 0-100（news_ai_score 另存，未分级为 null） */
  aiScore?: number | null
  aiScoredAt?: string | null
}

/** 电报条目领域类型（camelCase，前端使用）。 */
export interface TelegraphItem {
  clsMsgId: number
  title: string | null
  content: string | null
  category: string | null
  importance: number | null
  shared: number | null
  stockCodes: string[]
  publishTime: string
  /** cls.cn 原文链接，由 clsMsgId 派生 */
  sourceUrl: string
  /** AI 重要度 0-100（未分级为 null） */
  aiScore: number | null
}

/** 电报分页领域类型（camelCase，前端使用）。 */
export interface TelegraphPage {
  total: number
  page: number
  pageSize: number
  items: TelegraphItem[]
}
