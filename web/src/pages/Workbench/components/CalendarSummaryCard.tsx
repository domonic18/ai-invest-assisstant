import { Card, Empty, List, Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'

import type { CalendarEvent } from '@ai-invest/shared'
import { categoryMeta } from '@/pages/Calendar/categoryMeta'

interface CalendarSummaryCardProps {
  events?: CalendarEvent[]
  loading?: boolean
}

export function CalendarSummaryCard({ events, loading }: CalendarSummaryCardProps) {
  return (
    <Card
      variant="borderless"
      title="投资日历"
      extra={<Link to="/calendar" className="text-xs">全部日程</Link>}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : events?.length ? (
        <List
          dataSource={events}
          renderItem={(item) => (
            <List.Item className="!px-0">
              <div className="flex items-center gap-2 w-full min-w-0">
                <span className="text-xs text-gray-500 font-mono shrink-0">
                  {dayjs(item.eventTime).format('MM-DD HH:mm')}
                </span>
                <Tag color={categoryMeta(item.category).tagColor} className="!m-0 shrink-0">
                  {item.category}
                </Tag>
                <span className="text-sm truncate" title={item.title}>
                  {item.title}
                </span>
              </div>
            </List.Item>
          )}
        />
      ) : (
        <Empty description="暂无临近事件" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Card>
  )
}
