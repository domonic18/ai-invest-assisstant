import { Empty, List, Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'

import type { TelegraphItem } from '@ai-invest/shared'

import { FoldCard } from './FoldCard'

interface TelegraphCardProps {
  items?: TelegraphItem[]
  loading?: boolean
  className?: string
  stretch?: boolean
}

/** 概览只呈现固定条数（原型密度），其余引流到电报页。 */
const MAX_ITEMS = 10

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

/** 电报准实时徽标（红点 + 文案，镜像 /telegraph 页断流探针语义）。 */
function LiveBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-px rounded-full bg-red-500/10 text-red-400 text-[10px] font-semibold">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
      电报 10s 准实时
    </span>
  )
}

export function TelegraphCard({ items, loading, className, stretch }: TelegraphCardProps) {
  return (
    <FoldCard
      title={
        <span>
          要闻资讯 <LiveBadge />
        </span>
      }
      extra={<Link to="/telegraph" className="text-xs">更多电报</Link>}
      className={className}
      stretch={stretch}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : items?.length ? (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <List
            dataSource={items.slice(0, MAX_ITEMS)}
            renderItem={(item) => (
              <List.Item className="!px-0 !py-2.5">
                <div className="flex items-start gap-2.5 w-full min-w-0">
                  <span className="shrink-0 text-[11px] text-gray-500 font-mono mt-1">
                    {dayjs(item.publishTime).format('HH:mm')}
                  </span>
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
      ) : (
        <Empty description="暂无电报" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </FoldCard>
  )
}
