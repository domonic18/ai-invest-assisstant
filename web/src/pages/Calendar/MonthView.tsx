import dayjs, { type Dayjs } from 'dayjs'

import type { CalendarEvent } from '@ai-invest/shared'

import { categoryMeta } from './categoryMeta'

const DOW_LABELS = ['日', '一', '二', '三', '四', '五', '六']
const MAX_CHIPS = 3

interface MonthViewProps {
  month: Dayjs
  events: CalendarEvent[]
  onSelectEvent: (event: CalendarEvent) => void
}

export function MonthView({ month, events, onSelectEvent }: MonthViewProps) {
  const firstCell = month.startOf('month').startOf('week')
  const today = dayjs().startOf('day')
  const cells = Array.from({ length: 42 }, (_, i) => firstCell.add(i, 'day'))

  const eventsByDay = new Map<string, CalendarEvent[]>()
  for (const event of events) {
    const key = dayjs(event.eventTime).format('YYYY-MM-DD')
    const list = eventsByDay.get(key)
    if (list) list.push(event)
    else eventsByDay.set(key, [event])
  }

  return (
    <div>
      <div className="grid grid-cols-7 gap-1.5 mb-1">
        {DOW_LABELS.map((label) => (
          <div key={label} className="text-center text-xs text-gray-500 font-semibold py-1">
            {label}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1.5">
        {cells.map((date) => {
          const inMonth = date.isSame(month, 'month')
          const isToday = date.isSame(today, 'day')
          const dayEvents = eventsByDay.get(date.format('YYYY-MM-DD')) ?? []
          return (
            <div
              key={date.format('YYYY-MM-DD')}
              className={`min-h-[84px] rounded border p-1.5 ${
                inMonth ? 'bg-white/[0.03] border-white/10' : 'bg-transparent border-dashed border-white/5 opacity-50'
              } ${isToday ? '!border-blue-500' : ''}`}
            >
              <span
                className={`inline-flex w-5 h-5 items-center justify-center rounded-full text-xs tabular-nums ${
                  isToday ? 'bg-blue-500 text-white' : 'text-gray-400'
                }`}
              >
                {date.date()}
              </span>
              {dayEvents.slice(0, MAX_CHIPS).map((event) => (
                <div
                  key={event.id}
                  onClick={() => onSelectEvent(event)}
                  className={`mt-1 px-1.5 py-0.5 rounded text-[11px] leading-snug truncate cursor-pointer border-l-2 ${categoryMeta(event.category).chipClass}`}
                  title={event.title}
                >
                  {dayjs(event.eventTime).format('HH:mm')} {event.title}
                </div>
              ))}
              {dayEvents.length > MAX_CHIPS && (
                <div className="mt-1 text-[11px] text-gray-500">+{dayEvents.length - MAX_CHIPS}</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
