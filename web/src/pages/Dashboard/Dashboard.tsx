import { DatePicker, Typography } from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'

import { StockSearch } from '@/components/common/StockSearch'
import {
  useLimitUp,
  useMarketIndices,
  useMarketStats,
  useSectorOverview,
} from '@/hooks/useMarket'

import { AiReviewSection } from './components/AiReviewSection'
import { LimitUpSection } from './components/LimitUpSection'
import { MarketStatsSection } from './components/MarketStatsSection'
import { SectorSection } from './components/SectorSection'
import { WatchlistQuotesCard } from './components/WatchlistQuotesCard'

export function Dashboard() {
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null)
  const tradeDate = selectedDate?.format('YYYY-MM-DD')

  const { data: indices, isLoading: indicesLoading } = useMarketIndices(tradeDate)
  const { data: stats, isLoading: statsLoading } = useMarketStats(tradeDate)
  const { data: limitUp, isLoading: limitUpLoading } = useLimitUp(tradeDate)
  const { data: sectors, isLoading: sectorsLoading } = useSectorOverview(tradeDate)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <Typography.Title level={4} className="!mb-0">每日复盘</Typography.Title>
          <Typography.Text className="text-xs text-gray-500">
            AI 复盘报告 · 数据交易日 {stats?.tradeDate ?? limitUp?.tradeDate ?? '-'}
          </Typography.Text>
        </div>
        <div className="flex items-center gap-3">
          <DatePicker
            value={selectedDate}
            onChange={setSelectedDate}
            allowClear
            placeholder="选择复盘日期"
            disabledDate={(d) =>
              d.isAfter(dayjs(), 'day') || d.day() === 0 || d.day() === 6
            }
          />
          <StockSearch onSelect={(code) => window.location.assign(`/stock/${code}`)} />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <MarketStatsSection
            indices={indices}
            stats={stats}
            loading={indicesLoading || statsLoading}
            tradeDate={tradeDate}
          />
          <SectorSection data={sectors} loading={sectorsLoading} />
          <LimitUpSection data={limitUp} loading={limitUpLoading} />
        </div>

        <div className="space-y-6">
          <AiReviewSection tradeDate={tradeDate} />
          <WatchlistQuotesCard />
        </div>
      </div>
    </div>
  )
}
