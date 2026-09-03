import dayjs, { type Dayjs } from 'dayjs'

import type { CalendarEvent } from '@ai-invest/shared'

import { categoryMeta } from './categoryMeta'
import { eventTimeHm } from './eventTime'
import { mondayOf } from './weekRange'

const DOW_LABELS = ['一', '二', '三', '四', '五', '六', '日']

interface WeekViewProps {
  weekAnchor: Dayjs
  events: CalendarEvent[]
  onSelectEvent: (event: CalendarEvent) => void
}

export function WeekView({ weekAnchor, events, onSelectEvent }: WeekViewProps) {
  const monday = mondayOf(weekAnchor)
  const today = dayjs().startOf('day')
  const days = Array.from({ length: 7 }, (_, i) => monday.add(i, 'day'))

  const eventsByDay = new Map<string, CalendarEvent[]>()
  for (const event of events) {
    const key = dayjs(event.eventTime).format('YYYY-MM-DD')
    const list = eventsByDay.get(key)
    if (list) list.push(event)
    else eventsByDay.set(key, [event])
  }

  return (
    <div className="grid grid-cols-7 gap-2">
      {days.map((date, idx) => {
        const isToday = date.isSame(today, 'day')
        const dayEvents = eventsByDay.get(date.format('YYYY-MM-DD')) ?? []
        return (
          <div
            key={date.format('YYYY-MM-DD')}
            className={`rounded border p-2 min-h-[200px] ${
              isToday ? 'border-blue-500' : 'border-white/10 bg-white/[0.03]'
            }`}
          >
            <div
              className={`text-xs font-mono mb-2 ${isToday ? 'text-blue-400 font-semibold' : 'text-gray-500'}`}
            >
              {DOW_LABELS[idx]} · {date.format('MM-DD')}
              {isToday && ' 今天'}
            </div>
            {dayEvents.length === 0 ? (
              <div className="text-[11px] text-gray-600">暂无事件</div>
            ) : (
              dayEvents.map((event) => {
                const hm = eventTimeHm(event)
                return (
                  <div
                    key={event.id}
                    onClick={() => onSelectEvent(event)}
                    className={`mb-1.5 px-1.5 py-1 rounded text-[11px] leading-snug cursor-pointer border-l-2 ${categoryMeta(event.category).chipClass}`}
                  >
                    {hm ? (
                      <span className="font-mono">{hm}</span>
                    ) : (
                      <span className="font-bold">·</span>
                    )}{' '}
                    {event.title}
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
