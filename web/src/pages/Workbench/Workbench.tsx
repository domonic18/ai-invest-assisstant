import { Button, Empty, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'

import { useWorkbench } from '@/hooks/useWorkbench'

import { CalendarSummaryCard } from './components/CalendarSummaryCard'
import { CollectorEngineCard } from './components/CollectorEngineCard'
import { IndexStrip } from './components/IndexStrip'
import { QuickEntriesCard } from './components/QuickEntriesCard'
import { ReviewStatusCard } from './components/ReviewStatusCard'
import { SectorFlowCard } from './components/SectorFlowCard'
import { TelegraphCard } from './components/TelegraphCard'
import { WatchlistOverviewCard } from './components/WatchlistOverviewCard'

const WEEKDAYS = '日一二三四五六'

function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => dayjs())
  useEffect(() => {
    const timer = setInterval(() => setNow(dayjs()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

export function Workbench() {
  const { data, isLoading, isError, refetch } = useWorkbench()
  const now = useNow()

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
        <Typography.Text className="text-xs text-gray-500 font-mono" data-testid="workbench-clock">
          {now.format('YYYY-MM-DD')} 周{WEEKDAYS[now.day()]}{' '}
          {now.format('HH:mm:ss')}
        </Typography.Text>
      </div>

      <IndexStrip
        indices={data?.indices}
        globalIndices={data?.globalIndices}
        loading={isLoading}
      />

      {/* 行对齐网格：行内两卡等高（stretch），行序 复盘/日历 → 要闻/引擎 → 自选/板块 → 快捷入口 */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-5 items-stretch">
        <ReviewStatusCard
          status={data?.reviewStatus ?? null}
          review={data?.review ?? null}
          groups={data?.watchlistGroups}
          stats={data?.stats ?? undefined}
          loading={isLoading}
          className="xl:col-span-2"
          stretch
        />
        <CalendarSummaryCard events={data?.calendar} loading={isLoading} stretch />
        <TelegraphCard
          items={data?.telegraph}
          loading={isLoading}
          className="xl:col-span-2"
          stretch
        />
        <CollectorEngineCard status={data?.collectorStatus ?? null} loading={isLoading} stretch />
        <WatchlistOverviewCard
          groups={data?.watchlistGroups}
          loading={isLoading}
          className="xl:col-span-2"
          stretch
        />
        <SectorFlowCard items={data?.sectorFlow} loading={isLoading} stretch />
        <QuickEntriesCard className="xl:col-span-3" />
      </div>
    </div>
  )
}
