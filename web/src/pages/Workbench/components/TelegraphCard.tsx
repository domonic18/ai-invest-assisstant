import { Card, Empty, List, Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'

import type { TelegraphItem } from '@ai-invest/shared'

interface TelegraphCardProps {
  items?: TelegraphItem[]
  loading?: boolean
}

function importanceTag(importance: number | null) {
  if (importance === null) return null
  const presets: Record<number, { color: string; label: string }> = {
    3: { color: 'red', label: '重要' },
    2: { color: 'orange', label: '关注' },
    1: { color: 'blue', label: '一般' },
  }
  const preset = presets[importance] ?? { color: 'gold', label: `L${importance}` }
  return <Tag color={preset.color}>{preset.label}</Tag>
}

export function TelegraphCard({ items, loading }: TelegraphCardProps) {
  return (
    <Card
      variant="borderless"
      title="财联社电报"
      extra={<Link to="/telegraph" className="text-xs">更多电报</Link>}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : items?.length ? (
        <List
          dataSource={items}
          renderItem={(item) => (
            <List.Item className="!px-0">
              <div className="flex items-start gap-2 w-full min-w-0">
                <span className="text-xs text-gray-500 font-mono shrink-0 mt-0.5">
                  {dayjs(item.publishTime).format('HH:mm')}
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    {importanceTag(item.importance)}
                    {item.title ? (
                      <span className="text-sm font-medium truncate">{item.title}</span>
                    ) : null}
                  </div>
                  {!item.title && item.content && (
                    <div className="text-sm text-gray-400 truncate">{item.content}</div>
                  )}
                </div>
              </div>
            </List.Item>
          )}
        />
      ) : (
        <Empty description="暂无电报" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Card>
  )
}
