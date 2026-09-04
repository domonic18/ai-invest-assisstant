import { Empty, Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'

import type { CalendarEvent } from '@ai-invest/shared'
import { categoryMeta } from '@/pages/Calendar/categoryMeta'

import { FoldCard } from './FoldCard'

interface CalendarSummaryCardProps {
  events?: CalendarEvent[]
  loading?: boolean
  className?: string
  stretch?: boolean
}

export function CalendarSummaryCard({ events, loading, className, stretch }: CalendarSummaryCardProps) {
  return (
    <FoldCard
      title="投资日历 · 临近日程"
      extra={<Link to="/calendar" className="text-xs">进入完整日历</Link>}
      className={className}
      stretch={stretch}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : events?.length ? (
        events.map((item) => {
          const date = dayjs(item.eventTime)
          const isToday = date.isSame(dayjs(), 'day')
          return (
            <div
              key={item.id}
              className="flex items-start gap-2.5 py-2 border-b border-gray-800 last:border-b-0"
            >
              <span className="shrink-0 w-12 text-[11px] text-gray-500 font-mono leading-snug">
                {date.format('MM-DD')}
                {isToday && <br />}
                {isToday && <span className="text-amber-400 font-semibold">今日</span>}
              </span>
              <div className="min-w-0">
                <div className="text-xs text-gray-100 leading-normal">{item.title}</div>
                <div className="mt-1">
                  <Tag color={categoryMeta(item.category).tagColor}>{item.category}</Tag>
                </div>
              </div>
            </div>
          )
        })
      ) : (
        <Empty description="暂无临近事件" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </FoldCard>
  )
}
