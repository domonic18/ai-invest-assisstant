/** 财联社电报（news_telegraph）类型：camelCase wire + camelCase 领域类型。 */

import type { ApiScoreFactors } from './news'

/** 后端 GET /telegraph 分页响应。 */
export interface ApiTelegraphPage {
  total: number
  page: number
  pageSize: number
  items: ApiTelegraphResponse[]
}

/** 电报关联标的轻量快照（名称 + 当日涨跌幅）。 */
export interface ApiTelegraphStock {
  code: string
  name: string
  /** 当日涨跌幅（%）；实时/收盘/日 K 全部 miss 时为 null */
  changePct?: number | null
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
  /** 关联标的快照（与 stockCodes 同序；未富化时缺省） */
  stocks?: ApiTelegraphStock[]
  publishTime: string
  /** AI 重要度 0-100（news_ai_score 另存，未分级为 null） */
  aiScore?: number | null
  aiScoredAt?: string | null
  /** 评分构成三维（存量评分行无构成为 null） */
  aiFactors?: ApiScoreFactors | null
  /** 是否命中当前用户订阅关键词 */
  subscribed?: boolean | null
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
  /** 关联标的快照（名称 + 当日涨跌幅），未富化时为空 */
  stocks: ApiTelegraphStock[]
  publishTime: string
  /** cls.cn 原文链接，由 clsMsgId 派生 */
  sourceUrl: string
  /** AI 重要度 0-100（未分级为 null） */
  aiScore: number | null
  /** 评分构成三维（存量评分行无构成为 null） */
  aiFactors: ApiScoreFactors | null
  /** 是否命中当前用户订阅关键词 */
  subscribed: boolean
}

/** 电报分页领域类型（camelCase，前端使用）。 */
export interface TelegraphPage {
  total: number
  page: number
  pageSize: number
  items: TelegraphItem[]
}
