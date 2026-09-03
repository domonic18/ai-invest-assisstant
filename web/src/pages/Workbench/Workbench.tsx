import { Button, Empty, Typography } from 'antd'
import dayjs from 'dayjs'

import { useWorkbench } from '@/hooks/useWorkbench'

import { CalendarSummaryCard } from './components/CalendarSummaryCard'
import { IndexStrip } from './components/IndexStrip'
import { QuickEntriesCard } from './components/QuickEntriesCard'
import { ReviewSummaryCard } from './components/ReviewSummaryCard'
import { SectorFlowCard } from './components/SectorFlowCard'
import { TelegraphCard } from './components/TelegraphCard'
import { WatchlistOverviewCard } from './components/WatchlistOverviewCard'

const WEEKDAYS = '日一二三四五六'

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
    <div className="space-y-5">
      <div className="flex items-baseline justify-between">
        <Typography.Title level={4} className="!mb-0">工作台</Typography.Title>
        <Typography.Text className="text-xs text-gray-500">
          {dayjs().format('YYYY-MM-DD')} 周{WEEKDAYS[dayjs().day()]}
        </Typography.Text>
      </div>

      <IndexStrip
        indices={data?.indices}
        globalIndices={data?.globalIndices}
        loading={isLoading}
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-5">
        <div className="xl:col-span-2 space-y-5">
          <ReviewSummaryCard
            review={data?.review ?? null}
            stats={data?.stats ?? undefined}
            loading={isLoading}
          />
          <TelegraphCard items={data?.telegraph} loading={isLoading} />
          <WatchlistOverviewCard groups={data?.watchlistGroups} loading={isLoading} />
        </div>

        <div className="space-y-5">
          <CalendarSummaryCard events={data?.calendar} loading={isLoading} />
          <SectorFlowCard />
          <QuickEntriesCard />
        </div>
      </div>
    </div>
  )
}
