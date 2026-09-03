import { Table, Tag } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import type { CalendarEvent, CalendarEventCategory } from '@ai-invest/shared'

import { categoryMeta } from './categoryMeta'
import { eventTimeHm } from './eventTime'

interface ListViewProps {
  month: Dayjs
  events: CalendarEvent[]
  onSelectEvent: (event: CalendarEvent) => void
}

export function ListView({ month, events, onSelectEvent }: ListViewProps) {
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
            {hm ?? (
              <span className={`font-bold ${categoryMeta(record.category).dotClass}`}>
                ·
              </span>
            )}
          </span>
        )
      },
    },
    {
      title: '事件',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record: CalendarEvent) => (
        <a onClick={() => onSelectEvent(record)}>{title}</a>
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
      render: (symbols: string[]) =>
        symbols.length ? (
          <span className="font-mono">{symbols.join(' ')}</span>
        ) : (
          '-'
        ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 90,
      render: (source: string | null) => {
        if (!source) return '-'
        const labels: Record<string, string> = { fomc: '美联储', bls: 'BLS' }
        return labels[source] ?? source
      },
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
