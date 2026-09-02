/** 财联社电报（news_telegraph）类型：snake_case wire + camelCase 领域类型。 */

/** 后端 GET /telegraph 分页响应（snake_case）。 */
export interface ApiTelegraphPage {
  total: number
  page: number
  page_size: number
  items: ApiTelegraphResponse[]
}

/** 后端电报条目（snake_case）。 */
export interface ApiTelegraphResponse {
  cls_msg_id: number
  title: string | null
  content: string | null
  category: string | null
  importance: number | null
  shared: number | null
  stock_codes: string[] | null
  publish_time: string
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
}

/** 电报分页领域类型（camelCase，前端使用）。 */
export interface TelegraphPage {
  total: number
  page: number
  pageSize: number
  items: TelegraphItem[]
}
