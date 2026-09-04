import { Empty, List, Spin, Tag } from 'antd'
import dayjs from 'dayjs'

import type { TelegraphItem } from '@ai-invest/shared'

interface HotTimelineProps {
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

/** 实时热点时间线：财联社电报按发布时间倒序（10s 准实时），原型左栏规格。 */
export function HotTimeline({ items, loading }: HotTimelineProps) {
  if (loading && !items?.length) {
    return <div className="flex justify-center py-16"><Spin /></div>
  }
  if (!items?.length) {
    return <Empty description="暂无电报" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }
  return (
    <div className="h-[440px] overflow-y-auto pr-1">
      <List
        dataSource={items}
        renderItem={(item) => (
          <List.Item className="!px-0 !py-2.5">
            <div className="flex gap-3 w-full min-w-0">
              <div className="flex flex-col items-center shrink-0 w-11">
                <span className="w-1.5 h-1.5 rounded-full bg-[#5e6ad2]" />
                <span className="text-[11px] text-gray-500 font-mono mt-1">
                  {dayjs(item.publishTime).format('HH:mm')}
                </span>
              </div>
              <div className="min-w-0">
                <div className="text-[13px] text-gray-100 leading-normal line-clamp-2">
                  {item.title ?? item.content}
                </div>
                {(item.category || item.importance !== null) && (
                  <div className="flex gap-1.5 mt-1">
                    {importanceTag(item.importance)}
                    {item.category && <Tag>{item.category}</Tag>}
                  </div>
                )}
              </div>
            </div>
          </List.Item>
        )}
      />
    </div>
  )
}
