import dayjs, { type Dayjs } from 'dayjs'

import type { CalendarEvent } from '@ai-invest/shared'

import { categoryMeta } from './categoryMeta'
import { DOW_LABELS_SUN_FIRST, eventHitsWatchlist } from './eventMeta'
import { EventTimeDot } from './EventTimeDot'
import { eventTimeHm } from './eventTime'

import { DATE_FORMAT } from '@/utils/formatters'

const MAX_CHIPS = 3

interface MonthViewProps {
  month: Dayjs
  events: CalendarEvent[]
  selectedDay: Dayjs
  onSelectDay: (day: Dayjs) => void
  watchlistCodes: Set<string>
}

export function MonthView({
  month,
  events,
  selectedDay,
  onSelectDay,
  watchlistCodes,
}: MonthViewProps) {
  const firstCell = month.startOf('month').startOf('week')
  const today = dayjs().startOf('day')
  const cells = Array.from({ length: 42 }, (_, i) => firstCell.add(i, 'day'))

  const eventsByDay = new Map<string, CalendarEvent[]>()
  for (const event of events) {
    const key = dayjs(event.eventTime).format(DATE_FORMAT)
    const list = eventsByDay.get(key)
    if (list) list.push(event)
    else eventsByDay.set(key, [event])
  }

  return (
    <div>
      <div className="grid grid-cols-7 gap-1.5 mb-1">
        {DOW_LABELS_SUN_FIRST.map((label) => (
          <div key={label} className="text-center text-xs text-gray-500 font-semibold py-1">
            {label}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1.5">
        {cells.map((date) => {
          const inMonth = date.isSame(month, 'month')
          const isToday = date.isSame(today, 'day')
          const isSelected = date.isSame(selectedDay, 'day')
          const dayEvents = eventsByDay.get(date.format(DATE_FORMAT)) ?? []
          return (
            <div
              key={date.format(DATE_FORMAT)}
              onClick={() => inMonth && onSelectDay(date)}
              className={`min-h-[84px] rounded border p-1.5 ${
                inMonth
                  ? 'bg-white/[0.03] border-white/10 cursor-pointer'
                  : 'bg-transparent border-dashed border-white/5 opacity-50'
              } ${isToday || isSelected ? '!border-blue-500' : ''} ${
                isSelected ? 'shadow-[0_0_0_1px] shadow-blue-500' : ''
              }`}
            >
              <span
                className={`inline-flex w-5 h-5 items-center justify-center rounded-full text-xs tabular-nums ${
                  isToday ? 'bg-blue-500 text-white' : 'text-gray-400'
                }`}
              >
                {date.date()}
              </span>
              {dayEvents.slice(0, MAX_CHIPS).map((event) => {
                const hm = eventTimeHm(event)
                return (
                  <div
                    key={event.id}
                    className={`mt-1 px-1.5 py-0.5 rounded text-[11px] leading-snug truncate border-l-2 ${categoryMeta(event.category).chipClass}`}
                    title={event.title}
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
              })}
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
