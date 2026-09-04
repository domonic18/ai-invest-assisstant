import { useQueryClient } from '@tanstack/react-query'
import { Button, DatePicker, message, Typography } from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'

import { collectMarketData } from '@/api/market'
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
  const queryClient = useQueryClient()
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null)
  const [collecting, setCollecting] = useState(false)
  const tradeDate = selectedDate?.format('YYYY-MM-DD')
  const isPastDate = Boolean(tradeDate && dayjs(tradeDate).isBefore(dayjs(), 'day'))

  const { data: indices, isLoading: indicesLoading } = useMarketIndices(tradeDate)
  const { data: stats, isLoading: statsLoading } = useMarketStats(tradeDate)
  const { data: limitUp, isLoading: limitUpLoading } = useLimitUp(tradeDate)
  const { data: sectors, isLoading: sectorsLoading } = useSectorOverview(tradeDate)

  const handleCollect = async () => {
    if (!tradeDate) return
    setCollecting(true)
    try {
      await collectMarketData(tradeDate)
      message.success(
        '补采任务已提交后台执行：涨停/成交额约 1 分钟入库，板块资金约需 10 分钟，请稍后刷新查看',
        8,
      )
      await queryClient.invalidateQueries({ queryKey: ['market'] })
    } catch (err) {
      message.error(err instanceof Error ? err.message : '补采失败')
    } finally {
      setCollecting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
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
          {isPastDate && (
            <Button loading={collecting} onClick={handleCollect}>
              补采数据
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-6">
        <div className="xl:col-span-2 space-y-6">
          <MarketStatsSection
            indices={indices}
            stats={stats}
            loading={indicesLoading || statsLoading}
            tradeDate={tradeDate}
          />
          <SectorSection
            data={sectors}
            loading={sectorsLoading}
            pendingClose={
              sectors?.tradeDate === dayjs().format('YYYY-MM-DD') &&
              dayjs().hour() < 15
            }
            canBackfill={isPastDate}
          />
          <LimitUpSection
            data={limitUp}
            loading={limitUpLoading}
            pendingClose={
              limitUp?.tradeDate === dayjs().format('YYYY-MM-DD') &&
              dayjs().hour() < 15
            }
            canBackfill={isPastDate}
            tradeDate={tradeDate}
          />
        </div>

        <div className="space-y-6">
          <AiReviewSection tradeDate={tradeDate} />
          <WatchlistQuotesCard />
        </div>
      </div>
    </div>
  )
}
