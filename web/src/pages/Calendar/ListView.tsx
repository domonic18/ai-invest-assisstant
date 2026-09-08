import { Table, Tag } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import type { CalendarEvent, CalendarEventCategory } from '@ai-invest/shared'

import { categoryMeta } from './categoryMeta'
import { eventHitsWatchlist, sourceLabel } from './eventMeta'
import { EventTimeDot } from './EventTimeDot'
import { eventTimeHm } from './eventTime'

interface ListViewProps {
  month: Dayjs
  events: CalendarEvent[]
  onSelectDay: (day: Dayjs) => void
  watchlistCodes: Set<string>
}

export function ListView({ month, events, onSelectDay, watchlistCodes }: ListViewProps) {
  const columns = [
    {
      title: '日期 / 时间',
      key: 'time',
      width: 150,
      render: (_: unknown, record: CalendarEvent) => {
        const hm = eventTimeHm(record)
        return (
          <span className="font-mono tabular-nums">
            {dayjs(record.eventTime).format('MM-DD')}{' '}
            {hm ?? <EventTimeDot className={categoryMeta(record.category).dotClass} />}
          </span>
        )
      },
    },
    {
      title: '事件',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record: CalendarEvent) => (
        <a onClick={() => onSelectDay(dayjs(record.eventTime))}>{title}</a>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (category: CalendarEventCategory) => (
        <Tag color={categoryMeta(category).tagColor}>{category}</Tag>
      ),
    },
    {
      title: '影响市场',
      dataIndex: 'impactMarkets',
      key: 'impactMarkets',
      width: 180,
      render: (markets: string[]) => (markets.length ? markets.join(' · ') : '-'),
    },
    {
      title: '关联标的',
      dataIndex: 'relatedSymbols',
      key: 'relatedSymbols',
      width: 160,
      render: (symbols: string[], record: CalendarEvent) =>
        symbols.length ? (
          <span className="font-mono">
            {symbols.join(' ')}
            {eventHitsWatchlist(record, watchlistCodes) && (
              <span className="text-amber-400" title="关联标的命中自选股">
                {' '}
                ★
              </span>
            )}
          </span>
        ) : (
          '-'
        ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 130,
      render: (source: string | null) => sourceLabel(source),
    },
  ]

  return (
    <Table
      dataSource={events}
      columns={columns}
      rowKey="id"
      pagination={false}
      size="small"
      scroll={{ x: 'max-content' }}
      locale={{ emptyText: `${month.format('YYYY 年 M 月')}暂无事件` }}
    />
  )
}
