import dayjs from 'dayjs'

import type { CalendarEvent } from '@ai-invest/shared'

import { toBeijing } from '@/utils/beijing'

/** 无具体时刻（00:00 占位）的日级事件，时刻位渲染类别色 · 而非 00:00。
 * 判定与展示按北京墙钟，与浏览器时区无关。 */
export function isDateOnlyEvent(event: CalendarEvent): boolean {
  return toBeijing(dayjs(event.eventTime)).format('HH:mm') === '00:00'
}

/** 事件时刻 HH:mm（北京墙钟）；日级事件返回 null。 */
export function eventTimeHm(event: CalendarEvent): string | null {
  return isDateOnlyEvent(event) ? null : toBeijing(dayjs(event.eventTime)).format('HH:mm')
}
