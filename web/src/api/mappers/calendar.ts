import type { ApiCalendarEventResponse, CalendarEvent, CalendarEventCategory } from '@ai-invest/shared'

import { CALENDAR_CATEGORIES } from '@ai-invest/shared'

export function mapCalendarEvent(dto: ApiCalendarEventResponse): CalendarEvent {
  return {
    id: dto.id,
    eventTime: dto.eventTime,
    endTime: dto.endTime,
    title: dto.title,
    category: (CALENDAR_CATEGORIES as readonly string[]).includes(dto.category)
      ? (dto.category as CalendarEventCategory)
      : '会议',
    impactMarkets: dto.impactMarkets ?? [],
    source: dto.source,
    sourceUrl: dto.sourceUrl,
    relatedSymbols: dto.relatedSymbols ?? [],
  }
}
