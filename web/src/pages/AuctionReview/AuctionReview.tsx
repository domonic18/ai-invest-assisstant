import { Card, DatePicker, Empty, Spin, Typography } from 'antd'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useState } from 'react'

import { SourceNote } from '@/components/common/SourceNote'
import { useIndexAuctionTrend } from '@/hooks/useAuction'
import { useColorScheme } from '@/stores/settings'

const { RangePicker } = DatePicker

// 交易日 ≈ 自然日 × 1.5（含周末与节假日冗余，图表只展示有数据的交易日）
const TRADING_DAY_PRESETS: Array<{ label: string; value: [Dayjs, Dayjs] }> = [
  { label: '近 30 个交易日', value: [dayjs().subtract(45, 'day'), dayjs()] },
  { label: '近 60 个交易日', value: [dayjs().subtract(90, 'day'), dayjs()] },
  { label: '近 120 个交易日', value: [dayjs().subtract(180, 'day'), dayjs()] },
]

// 与 Excel 图一致：上证=橙、科创50=蓝、创业板=绿（series 顺序由后端固定）
const SERIES_COLORS = ['#ED7D31', '#4472C4', '#70AD47']

function formatDateLabel(iso: string): string {
  const [, month, day] = iso.split('-')
  return `${Number(month)}月${Number(day)}日`
}

export function AuctionReview() {
  useColorScheme()
  // null = 默认近 30 个交易日（由后端 days 参数决定）
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null)
  const { data, isLoading, error } = useIndexAuctionTrend({
    startDate: range?.[0].format('YYYY-MM-DD'),
    endDate: range?.[1].format('YYYY-MM-DD'),
  })

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    color: SERIES_COLORS,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      valueFormatter: (value) =>
        typeof value === 'number' ? `${value.toFixed(2)} 亿` : '-',
    },
    legend: {
      bottom: 0,
      textStyle: { color: '#8c8c8c', fontSize: 10 },
      itemWidth: 14,
      itemHeight: 2,
      icon: 'rect',
    },
    grid: { left: 60, right: 30, top: 30, bottom: 70 },
    xAxis: {
      type: 'category',
      data: (data?.dates ?? []).map(formatDateLabel),
      axisLabel: { color: '#8c8c8c', fontSize: 10, rotate: 45 },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#3a3f4b' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      name: '亿元',
      nameTextStyle: { color: '#8c8c8c', fontSize: 10 },
      axisLabel: { color: '#8c8c8c', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    },
    series: (data?.series ?? []).map((s) => ({
      name: s.name,
      type: 'line',
      smooth: false,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { width: 1.5 },
      connectNulls: false,
      data: s.values,
      label: {
        show: true,
        position: 'top',
        fontSize: 10,
        color: 'inherit',
        formatter: (params) =>
          typeof params.value === 'number' ? params.value.toFixed(2) : '',
      },
    })),
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Typography.Title level={4} className="!mb-0">
          集合竞价
        </Typography.Title>
        <RangePicker
          value={range}
          onChange={(dates) => setRange(dates as [Dayjs, Dayjs] | null)}
          presets={TRADING_DAY_PRESETS}
          placeholder={['开始日期', '结束日期']}
          size="small"
          allowClear
        />
      </div>
      <Card variant="borderless">
        {isLoading ? (
          <div className="flex justify-center py-24">
            <Spin />
          </div>
        ) : error || !data || data.dates.length === 0 ? (
          <Empty
            className="py-16"
            description="暂无集合竞价数据（指数竞价采集任务交易日 9:26~9:29 运行后可用）"
          />
        ) : (
          <>
            <ReactECharts option={option} style={{ height: '480px', width: '100%' }} notMerge />
            <SourceNote>
              指数 9:25 集合竞价成交额由 tushare stk_auction 聚合成分股 9:25 撮合数据计算
            </SourceNote>
          </>
        )}
      </Card>
    </div>
  )
}
