/** 投资日历（calendar_event）类型：camelCase wire（CamelModel）+ camelCase 领域类型。 */

export const CALENDAR_CATEGORIES = ['宏观', '央行动态', '新股', '解禁', '财报', '会议'] as const

export type CalendarEventCategory = (typeof CALENDAR_CATEGORIES)[number]

/** 后端 GET /calendar/events 响应项（camelCase wire）。 */
export interface ApiCalendarEventResponse {
  id: number
  eventTime: string
  endTime: string | null
  title: string
  category: string
  impactMarkets: string[] | null
  source: string | null
  sourceUrl: string | null
  relatedSymbols: string[] | null
}

/** 日历事件领域类型（camelCase，前端使用）。 */
export interface CalendarEvent {
  id: number
  eventTime: string
  endTime: string | null
  title: string
  category: CalendarEventCategory
  impactMarkets: string[]
  source: string | null
  sourceUrl: string | null
  relatedSymbols: string[]
}
