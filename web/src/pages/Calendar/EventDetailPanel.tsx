import { Card, Tag, Tooltip } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import type { ReactNode } from 'react'

import type { CalendarEvent } from '@ai-invest/shared'

import { formatDate, formatDateTime } from '@/utils/formatters'

import { categoryMeta } from './categoryMeta'
import { DOW_LABELS_SUN_FIRST, eventHitsWatchlist, sourceLabel } from './eventMeta'
import { isDateOnlyEvent } from './eventTime'

interface EventDetailPanelProps {
  day: Dayjs
  events: CalendarEvent[]
  watchlistCodes: Set<string>
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2 text-xs">
      <span className="w-16 shrink-0 opacity-50">{label}</span>
      <span className="min-w-0">{children}</span>
    </div>
  )
}

/** 右栏常驻事件详情：选中日事件逐条展开（时间/市场/标的/来源），替代原抽屉交互。 */
export function EventDetailPanel({ day, events, watchlistCodes }: EventDetailPanelProps) {
  const isToday = day.isSame(dayjs(), 'day')
  const dayLabel = `${day.format('MM-DD')} 周${DOW_LABELS_SUN_FIRST[day.day()]}${isToday ? ' · 今天' : ''}`

  return (
    <Card
      variant="borderless"
      title="事件详情"
      extra={<span className="text-xs opacity-50">{dayLabel}</span>}
    >
      {events.length === 0 ? (
        <div className="py-2 text-xs opacity-50">
          该日暂无事件，点击左侧月历任一日期查看事件详情。
        </div>
      ) : (
        <div className="divide-y divide-white/5">
          {events.map((event) => {
            const starred = eventHitsWatchlist(event, watchlistCodes)
            return (
              <div key={event.id} className="space-y-2 py-3 first:pt-0 last:pb-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Tag color={categoryMeta(event.category).tagColor} className="!m-0">
                    {event.category}
                  </Tag>
                  <span className="text-sm font-semibold">{event.title}</span>
                  {starred && (
                    <Tooltip title="关联标的命中自选股">
                      <span className="text-xs text-amber-400">★</span>
                    </Tooltip>
                  )}
                </div>
                <div className="space-y-1">
                  <DetailRow label="事件时间">
                    <span className="font-mono">
                      {isDateOnlyEvent(event)
                        ? formatDate(event.eventTime)
                        : formatDateTime(event.eventTime)}
                    </span>
                  </DetailRow>
                  {event.endTime &&
                    !dayjs(event.endTime).isSame(dayjs(event.eventTime), 'minute') && (
                      <DetailRow label="结束时间">
                        <span className="font-mono">{formatDateTime(event.endTime)}</span>
                      </DetailRow>
                    )}
                  <DetailRow label="影响市场">
                    {event.impactMarkets.length ? event.impactMarkets.join(' · ') : '—'}
                  </DetailRow>
                  <DetailRow label="关联标的">
                    <span className="font-mono">
                      {event.relatedSymbols.length ? event.relatedSymbols.join('、') : '—'}
                      {starred && <span className="text-amber-400"> ★</span>}
                    </span>
                  </DetailRow>
                  <DetailRow label="来源">
                    {event.sourceUrl ? (
                      <a href={event.sourceUrl} target="_blank" rel="noreferrer">
                        {sourceLabel(event.source)}
                      </a>
                    ) : (
                      sourceLabel(event.source)
                    )}
                  </DetailRow>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
