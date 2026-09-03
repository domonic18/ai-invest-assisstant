import { Card } from 'antd'

import type { GlobalIndexQuote, IndexQuote, MarketStats } from '@ai-invest/shared'
import { SourceNote } from '@/components/common/SourceNote'
import { MarketStatsSection } from '@/pages/Dashboard/components/MarketStatsSection'

import { GlobalIndicesRow } from './GlobalIndicesRow'

interface MarketSnapshotCardProps {
  indices?: IndexQuote[]
  stats?: MarketStats
  globalIndices?: GlobalIndexQuote[]
  loading?: boolean
}

export function MarketSnapshotCard({
  indices,
  stats,
  globalIndices,
  loading,
}: MarketSnapshotCardProps) {
  const isLoading = loading ?? false

  return (
    <div className="space-y-4">
      <MarketStatsSection indices={indices} stats={stats} loading={isLoading} />
      <Card variant="borderless" title="全球指标">
        <GlobalIndicesRow indices={globalIndices} loading={isLoading} />
        <SourceNote>黄金 / 美元指数 / 美债收益率，取自本地日 K 最新收盘</SourceNote>
      </Card>
    </div>
  )
}
