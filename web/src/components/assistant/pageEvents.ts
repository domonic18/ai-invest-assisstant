import type { PageAssistantResult } from '@/stores/assistant'

/**
 * 页面回写事件注册表。
 *
 * 后端工具返回值携带 `__event__`（`page_event()` 构造），SSE custom 通道
 * 与 updates 通道都会把事件送到前端；本注册表是前端唯一的映射点：
 * 新业务域在此登记 parse 规则与查看按钮文案，再用
 * `usePageAssistantResult` 在页面订阅即可，无需改动其他管线代码。
 */
export interface PageEventDefinition {
  /** 事件类型标识（后端 page_event 的 type，约定 `<domain>.complete`） */
  eventType: string
  /** 分析完成后在对话内渲染的查看按钮文案 */
  actionLabel: string
  /** 原始事件（snake_case 字段）→ 强类型页面结果 */
  parse: (event: Record<string, unknown>) => PageAssistantResult
}

export const PAGE_EVENT_DEFINITIONS: readonly PageEventDefinition[] = [
  {
    eventType: 'industry_chain.analysis_complete',
    actionLabel: '查看产业链图谱',
    parse: (e) => ({
      type: 'industry_chain.analysis_complete',
      industry: String(e.industry ?? ''),
      versionId: Number(e.version_id),
      versionNo: Number(e.version_no),
      createdAt: e.created_at ? String(e.created_at) : undefined,
    }),
  },
  {
    eventType: 'stock_daily_analysis.complete',
    actionLabel: '查看个股分析结果',
    parse: (e) => ({
      type: 'stock_daily_analysis.complete',
      stockCode: String(e.stock_code ?? ''),
      tradeDate: String(e.trade_date ?? ''),
    }),
  },
]

const definitionsByType = new Map(
  PAGE_EVENT_DEFINITIONS.map((definition) => [definition.eventType, definition]),
)

export interface ParsedPageEvent {
  result: PageAssistantResult
  actionLabel: string
}

/** 识别已注册的页面回写事件；未注册类型返回 null。 */
export function parsePageEvent(event: unknown): ParsedPageEvent | null {
  if (typeof event !== 'object' || event === null) return null
  const e = event as Record<string, unknown>
  const definition = definitionsByType.get(String(e.type))
  if (!definition) return null
  return { result: definition.parse(e), actionLabel: definition.actionLabel }
}
