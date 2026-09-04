import { Descriptions, Drawer, Tag, Typography } from 'antd'
import dayjs from 'dayjs'

import type { CalendarEvent } from '@ai-invest/shared'

import { formatDate, formatDateTime } from '@/utils/formatters'

import { categoryMeta } from './categoryMeta'
import { isDateOnlyEvent } from './eventTime'

interface EventDrawerProps {
  event: CalendarEvent | null
  onClose: () => void
}

export function EventDrawer({ event, onClose }: EventDrawerProps) {
  return (
    <Drawer open={!!event} onClose={onClose} title={event?.title} width={420}>
      {event && (
        <div className="space-y-4">
          <Tag color={categoryMeta(event.category).tagColor}>{event.category}</Tag>
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="事件时间">
              {isDateOnlyEvent(event)
                ? formatDate(event.eventTime)
                : formatDateTime(event.eventTime)}
            </Descriptions.Item>
            {event.endTime && !dayjs(event.endTime).isSame(dayjs(event.eventTime), 'minute') && (
              <Descriptions.Item label="结束时间">
                {formatDateTime(event.endTime)}
              </Descriptions.Item>
            )}
            <Descriptions.Item label="影响市场">
              {event.impactMarkets.length ? (
                <span>
                  {event.impactMarkets.map((m) => (
                    <Tag key={m}>{m}</Tag>
                  ))}
                </span>
              ) : (
                '-'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="关联标的">
              {event.relatedSymbols.length ? (
                <span className="font-mono">{event.relatedSymbols.join('、')}</span>
              ) : (
                '-'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="来源">
              {event.source ? (
                event.sourceUrl ? (
                  <Typography.Link href={event.sourceUrl} target="_blank" rel="noreferrer">
                    {event.sourceUrl}
                  </Typography.Link>
                ) : (
                  event.source
                )
              ) : (
                '-'
              )}
            </Descriptions.Item>
          </Descriptions>
        </div>
      )}
    </Drawer>
  )
}
