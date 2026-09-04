import { Empty, Spin, Tag } from 'antd'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import type {
  WorkbenchAiStatus,
  WorkbenchWatchlistGroup,
} from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { changeColor, formatPercent } from '@/utils/formatters'

import { FoldCard } from './FoldCard'

interface WatchlistOverviewCardProps {
  groups?: WorkbenchWatchlistGroup[]
  loading?: boolean
  className?: string
  stretch?: boolean
}

const AI_STATUS_META: Record<
  WorkbenchAiStatus,
  { color: 'green' | 'gold' | 'default'; label: string }
> = {
  ready: { color: 'green', label: 'AI 已生成' },
  pending: { color: 'gold', label: '待生成' },
  off: { color: 'default', label: '未开启' },
}

export function WatchlistOverviewCard({
  groups,
  loading,
  className,
  stretch,
}: WatchlistOverviewCardProps) {
  useColorScheme()
  const [activeId, setActiveId] = useState<number | null>(null)

  const active: WorkbenchWatchlistGroup | undefined =
    groups?.find((g) => g.id === activeId) ?? groups?.[0]

  return (
    <FoldCard
      title="自选股概览"
      extra={<Link to="/watchlist" className="text-xs">管理分组</Link>}
      className={className}
      stretch={stretch}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : !groups?.length ? (
        <Empty description="暂无自选股" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="flex flex-col h-full">
          <div className="flex gap-2 flex-wrap mb-3">
            {groups.map((group) => (
              <button
                key={group.id}
                type="button"
                onClick={() => setActiveId(group.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border transition-colors ${
                  group.id === active?.id
                    ? 'bg-[#5e6ad2]/10 border-[#5e6ad2] text-[#a5abeb]'
                    : 'bg-[#181a21] border-gray-800 text-gray-400 hover:border-gray-600'
                }`}
              >
                {group.name}
                {group.aiReviewEnabled ? (
                  <span className="text-[10px] text-green-500">● AI 复盘</span>
                ) : (
                  <span className="text-[10px] text-gray-600">○</span>
                )}
              </button>
            ))}
          </div>

          {!active || active.items.length === 0 ? (
            <Empty description="该分组暂无自选股" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            active.items.map((stock) => (
              <div
                key={stock.code}
                className="flex items-center gap-3 py-2.5 border-b border-gray-800 last:border-b-0"
              >
                <span className="w-[130px] shrink-0 text-[13px] truncate">
                  <Link to={`/stock/${stock.code}`} className="hover:underline">
                    {stock.name ?? stock.code}
                  </Link>
                  <span className="ml-1.5 text-[11px] text-gray-500 font-mono">
                    {stock.code}
                  </span>
                </span>
                <span className="w-[72px] shrink-0 text-right font-mono text-[13px]">
                  {stock.price != null ? stock.price.toFixed(2) : '-'}
                </span>
                <span
                  className={`w-[72px] shrink-0 text-right font-mono text-[13px] font-semibold ${changeColor(stock.changePct)}`}
                >
                  {stock.changePct != null ? formatPercent(stock.changePct) : '-'}
                </span>
                <span className="flex-1 min-w-0 hidden lg:block text-[11px] text-gray-400 leading-normal line-clamp-2">
                  {stock.aiSummary ?? ''}
                </span>
                <span className="shrink-0">
                  <Tag color={AI_STATUS_META[stock.aiStatus].color}>
                    {AI_STATUS_META[stock.aiStatus].label}
                  </Tag>
                </span>
              </div>
            ))
          )}

          <div className="flex-1" />
          <div className="text-[10px] text-gray-500 pt-2.5 border-t border-dashed border-gray-800">
            AI 生成，不构成投资建议 · 仅开启 AI 复盘的分组在盘后定时批量生成
          </div>
        </div>
      )}
    </FoldCard>
  )
}
