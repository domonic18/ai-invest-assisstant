import { Button, Empty, Typography } from 'antd'

import { useWorkbench } from '@/hooks/useWorkbench'
import { WatchlistQuotesCard } from '@/pages/Dashboard/components/WatchlistQuotesCard'

import { CalendarSummaryCard } from './components/CalendarSummaryCard'
import { MarketSnapshotCard } from './components/MarketSnapshotCard'
import { ReviewSummaryCard } from './components/ReviewSummaryCard'
import { TelegraphCard } from './components/TelegraphCard'

export function Workbench() {
  const { data, isLoading, isError, refetch } = useWorkbench()

  if (isError) {
    return (
      <div className="py-12">
        <Empty description="工作台数据加载失败">
          <Button onClick={() => refetch()}>重新加载</Button>
        </Empty>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <Typography.Title level={4} className="!mb-0">工作台</Typography.Title>
        <Typography.Text className="text-xs text-gray-500">
          市场快览 · AI 复盘 · 财联社电报 · 投资日历 · 自选行情
        </Typography.Text>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-6">
        <div className="xl:col-span-2 space-y-6">
          <MarketSnapshotCard
            indices={data?.indices}
            stats={data?.stats ?? undefined}
            globalIndices={data?.globalIndices}
            loading={isLoading}
          />
          <ReviewSummaryCard review={data?.review ?? null} loading={isLoading} />
          <TelegraphCard items={data?.telegraph} loading={isLoading} />
        </div>

        <div className="space-y-6">
          <CalendarSummaryCard events={data?.calendar} loading={isLoading} />
          <WatchlistQuotesCard quotes={data?.watchlist} loading={isLoading} />
        </div>
      </div>
    </div>
  )
}
