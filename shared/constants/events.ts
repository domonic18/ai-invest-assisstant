/**
 * page_event 事件类型注册表（与后端 `page_event()` 构造点一一对应）。
 *
 * 约定命名 `<domain>.complete`；前端 stores/assistant.ts 的结果联合类型、
 * pageEvents.ts 注册表与页面 `usePageAssistantResult` 订阅均从此取值，
 * 禁止另行硬编码事件字符串。
 */
export const PAGE_EVENT_TYPES = {
  chainAnalysis: 'industry_chain.analysis.complete',
  stockDailyAnalysis: 'stock_daily_analysis.complete',
  marketDailyReview: 'market_daily_review.complete',
  limitUpAttribution: 'limit_up_attribution.complete',
  sectorAnomaly: 'sector_anomaly.complete',
  stockAnomaly: 'stock_anomaly.complete',
} as const

export type PageEventType = (typeof PAGE_EVENT_TYPES)[keyof typeof PAGE_EVENT_TYPES]
