import { PAGE_EVENT_TYPES, type PageEventType } from '@ai-invest/shared'

import type {
  ChainAnalysisResult,
  PageAssistantResult,
  StockDailyAnalysisResult,
} from '@/stores/assistant'

/**
 * 页面回写事件注册表。
 *
 * 后端工具返回值携带 `__event__`（`page_event()` 构造），SSE custom 通道
 * 与 updates 通道都会把事件送到前端；本注册表是前端唯一的映射点：
 * 新业务域在此登记 parse 规则、查看按钮文案与结果页路由，再用
 * `usePageAssistantResult` 在页面订阅即可，无需改动其他管线代码。
 */
export interface PageEventDefinition<T extends PageAssistantResult = PageAssistantResult> {
  /** 事件类型标识（后端 page_event 的 type，约定 `<domain>.complete`） */
  eventType: PageEventType
  /** 分析完成后在对话内渲染的查看按钮文案 */
  actionLabel: string
  /** 结果展示页路由：会话内查看按钮点击后导航至此（任意页面触发均可直达） */
  path(result: T): string
  /** 原始事件（snake_case 字段）→ 强类型页面结果 */
  parse(event: Record<string, unknown>): T
}

export const PAGE_EVENT_DEFINITIONS: readonly PageEventDefinition[] = [
  {
    eventType: PAGE_EVENT_TYPES.chainAnalysis,
    actionLabel: '查看产业链图谱',
    path: (r: ChainAnalysisResult) => `/chain/${encodeURIComponent(r.industry)}`,
    parse: (e) => ({
      type: PAGE_EVENT_TYPES.chainAnalysis,
      industry: String(e.industry ?? ''),
      versionId: Number(e.version_id),
      versionNo: Number(e.version_no),
      createdAt: e.created_at ? String(e.created_at) : undefined,
    }),
  },
  {
    eventType: PAGE_EVENT_TYPES.stockDailyAnalysis,
    actionLabel: '查看个股分析结果',
    path: (r: StockDailyAnalysisResult) => `/stock/${encodeURIComponent(r.stockCode)}`,
    parse: (e) => ({
      type: PAGE_EVENT_TYPES.stockDailyAnalysis,
      stockCode: String(e.stock_code ?? ''),
      tradeDate: String(e.trade_date ?? ''),
    }),
  },
  {
    eventType: PAGE_EVENT_TYPES.marketDailyReview,
    actionLabel: '查看复盘结果',
    path: () => '/review',
    parse: (e) => ({
      type: PAGE_EVENT_TYPES.marketDailyReview,
      tradeDate: String(e.trade_date ?? ''),
    }),
  },
  {
    eventType: PAGE_EVENT_TYPES.limitUpAttribution,
    actionLabel: '查看涨停归因',
    path: () => '/review',
    parse: (e) => ({
      type: PAGE_EVENT_TYPES.limitUpAttribution,
      tradeDate: String(e.trade_date ?? ''),
    }),
  },
  {
    eventType: PAGE_EVENT_TYPES.sectorAnomaly,
    actionLabel: '查看板块异动',
    path: () => '/anomaly/sector',
    parse: (e) => ({
      type: PAGE_EVENT_TYPES.sectorAnomaly,
      tradeDate: String(e.trade_date ?? ''),
    }),
  },
  {
    eventType: PAGE_EVENT_TYPES.stockAnomaly,
    actionLabel: '查看个股异动',
    path: () => '/anomaly/stock',
    parse: (e) => ({
      type: PAGE_EVENT_TYPES.stockAnomaly,
      tradeDate: String(e.trade_date ?? ''),
    }),
  },
]

const definitionsByType = new Map<string, PageEventDefinition>(
  PAGE_EVENT_DEFINITIONS.map((definition) => [definition.eventType, definition]),
)

export interface ParsedPageEvent {
  result: PageAssistantResult
  actionLabel: string
  path: string
}

/** 识别已注册的页面回写事件；未注册类型返回 null。 */
export function parsePageEvent(event: unknown): ParsedPageEvent | null {
  if (typeof event !== 'object' || event === null) return null
  const e = event as Record<string, unknown>
  const definition = definitionsByType.get(String(e.type))
  if (!definition) return null
  const result = definition.parse(e)
  return { result, actionLabel: definition.actionLabel, path: definition.path(result) }
}
