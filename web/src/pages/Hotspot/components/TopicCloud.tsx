import { Empty, Spin } from 'antd'
import { useMemo } from 'react'

import type { SectorFundFlow } from '@ai-invest/shared'

import { useLatestDaySectors } from '@/hooks/useHotspot'
import { formatAmount, formatPercent } from '@/utils/formatters'

/** 话题云取最新交易日涨幅前 N 板块（原型 16 个标签）。 */
const CLOUD_LIMIT = 16

/** 热度分层：按涨幅名次降档（红 → amber → 蓝 → 主题色 → 灰），字号随热度递减。 */
function tierClass(rank: number): string {
  if (rank === 0) return 'text-[1.4rem] font-bold bg-red-500/10 text-red-500'
  if (rank === 1) return 'text-[1.3rem] font-bold bg-red-500/10 text-red-500'
  if (rank === 2) return 'text-[1.2rem] font-semibold bg-amber-500/10 text-amber-500'
  if (rank === 3) return 'text-[1.1rem] bg-amber-500/10 text-amber-500'
  if (rank === 4) return 'text-[1.05rem] bg-sky-500/10 text-sky-400'
  if (rank === 5) return 'text-[1rem] bg-sky-500/10 text-sky-400'
  if (rank <= 8) return 'text-[0.95rem] bg-[#5e6ad2]/15 text-[#8b94e0]'
  if (rank <= 11) return 'text-[0.85rem] bg-gray-800 text-gray-400'
  return 'text-[0.8rem] bg-gray-800 text-gray-400'
}

function pickTopics(items: SectorFundFlow[]): SectorFundFlow[] {
  return items
    .filter((it) => it.changePct !== null)
    .sort((a, b) => (b.changePct ?? 0) - (a.changePct ?? 0))
    .slice(0, CLOUD_LIMIT)
}

/** 热点话题云：最新交易日涨幅 TOP 板块按热度分层着色（原型全宽卡）。 */
export function TopicCloud() {
  const { data, isLoading } = useLatestDaySectors()
  const topics = useMemo(() => pickTopics(data ?? []), [data])

  if (isLoading) {
    return <div className="flex justify-center py-12"><Spin /></div>
  }
  if (!topics.length) {
    return <Empty description="暂无板块数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }
  return (
    <div className="flex flex-wrap items-center justify-center gap-1 py-2">
      {topics.map((topic, rank) => (
        <span
          key={`${topic.sectorCode}-${topic.sectorType}`}
          title={`涨幅 ${formatPercent(topic.changePct ?? 0)} · 主力净流入 ${formatAmount(topic.mainNetInflow)}`}
          className={`m-0.5 cursor-default rounded-xl px-3 py-1 leading-normal transition-transform hover:-translate-y-px ${tierClass(rank)}`}
        >
          {topic.sectorName}
        </span>
      ))}
    </div>
  )
}
