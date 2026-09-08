import { Empty, Spin, Tag } from 'antd'
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

/** 与后端 _TELEGRAPH_PAGE_SIZE 对齐；行在 stretch 卡内均匀分布铺满等高卡。 */
const MAX_ITEMS = 12

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

/** 电报准实时徽标（红点 + 文案，镜像 /news 电报视图断流探针语义）。 */
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
      extra={<Link to="/news" className="text-xs">更多电报</Link>}
      className={className}
      stretch={stretch}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : items?.length ? (
        <div className="flex flex-1 min-h-0 flex-col overflow-y-auto">
          {items.slice(0, MAX_ITEMS).map((item) => (
            <div
              key={item.clsMsgId}
              className="flex flex-1 shrink-0 items-center gap-2.5 py-2.5 border-b border-gray-800 last:border-b-0"
            >
              <span className="shrink-0 text-[11px] text-gray-500 font-mono">
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
          ))}
        </div>
      ) : (
        <Empty description="暂无电报" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </FoldCard>
  )
}
