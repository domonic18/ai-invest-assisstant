import dayjs, { type Dayjs } from 'dayjs'

import type { CalendarEvent } from '@ai-invest/shared'

import { categoryMeta } from './categoryMeta'
import { eventHitsWatchlist } from './eventMeta'
import { EventTimeDot } from './EventTimeDot'
import { eventTimeHm } from './eventTime'
import { mondayOf } from './weekRange'

import { DATE_FORMAT } from '@/utils/formatters'

const DOW_LABELS = ['一', '二', '三', '四', '五', '六', '日']

interface WeekViewProps {
  weekAnchor: Dayjs
  events: CalendarEvent[]
  selectedDay: Dayjs
  onSelectDay: (day: Dayjs) => void
  watchlistCodes: Set<string>
}

export function WeekView({
  weekAnchor,
  events,
  selectedDay,
  onSelectDay,
  watchlistCodes,
}: WeekViewProps) {
  const monday = mondayOf(weekAnchor)
  const today = dayjs().startOf('day')
  const days = Array.from({ length: 7 }, (_, i) => monday.add(i, 'day'))

  const eventsByDay = new Map<string, CalendarEvent[]>()
  for (const event of events) {
    const key = dayjs(event.eventTime).format(DATE_FORMAT)
    const list = eventsByDay.get(key)
    if (list) list.push(event)
    else eventsByDay.set(key, [event])
  }

  return (
    <div className="grid grid-cols-7 gap-2">
      {days.map((date, idx) => {
        const isToday = date.isSame(today, 'day')
        const isSelected = date.isSame(selectedDay, 'day')
        const dayEvents = eventsByDay.get(date.format(DATE_FORMAT)) ?? []
        return (
          <div
            key={date.format(DATE_FORMAT)}
            onClick={() => onSelectDay(date)}
            className={`rounded border p-2 min-h-[200px] cursor-pointer ${
              isToday || isSelected ? 'border-blue-500' : 'border-white/10 bg-white/[0.03]'
            } ${isSelected ? 'shadow-[0_0_0_1px] shadow-blue-500' : ''}`}
          >
            <div
              className={`text-xs font-mono mb-2 ${isToday ? 'text-blue-400 font-semibold' : 'text-gray-500'}`}
            >
              {DOW_LABELS[idx]} · {date.format('MM-DD')}
              {isToday && ' 今天'}
            </div>
            {dayEvents.length === 0 ? (
              <div className="text-[11px] text-gray-600">{idx >= 5 ? '休市' : '暂无事件'}</div>
            ) : (
              dayEvents.map((event) => {
                const hm = eventTimeHm(event)
                return (
                  <div
                    key={event.id}
                    className={`mb-1.5 px-1.5 py-1 rounded text-[11px] leading-snug border-l-2 ${categoryMeta(event.category).chipClass}`}
                  >
                    {hm ? (
                      <span className="font-mono">{hm}</span>
                    ) : (
                      <EventTimeDot />
                    )}{' '}
                    {event.title}
                    {eventHitsWatchlist(event, watchlistCodes) && (
                      <span className="text-amber-400"> ★</span>
                    )}
                  </div>
                )
              })
            )}
          </div>
        )
      })}
    </div>
  )
}
