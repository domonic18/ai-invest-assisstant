import dayjs from 'dayjs'

import type { CalendarEvent } from '@ai-invest/shared'

/** 无具体时刻（00:00 占位）的日级事件，时刻位渲染类别色 · 而非 00:00。 */
export function isDateOnlyEvent(event: CalendarEvent): boolean {
  return dayjs(event.eventTime).format('HH:mm') === '00:00'
}

/** 事件时刻 HH:mm；日级事件返回 null。 */
export function eventTimeHm(event: CalendarEvent): string | null {
  return isDateOnlyEvent(event) ? null : dayjs(event.eventTime).format('HH:mm')
}
