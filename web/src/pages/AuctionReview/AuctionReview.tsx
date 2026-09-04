import { DownloadOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Card, DatePicker, Empty, Spin, Typography } from 'antd'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useMemo, useState } from 'react'

import { SourceNote } from '@/components/common/SourceNote'
import { useIndexAuctionTrend } from '@/hooks/useAuction'
import { ChartColors } from '@/theme/colors'
import { useColorScheme } from '@/stores/settings'

import { AuctionStatsCards } from './components/AuctionStatsCards'
import { AuctionStatsTable } from './components/AuctionStatsTable'
import {
  buildDailyStats,
  downloadCsv,
  presetToRange,
  statsToCsv,
  TRADING_DAY_PRESETS,
} from './utils'

const { RangePicker } = DatePicker

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
  const [pickerValue, setPickerValue] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const { data, isLoading, error } = useIndexAuctionTrend({
    startDate: range?.[0].format('YYYY-MM-DD'),
    endDate: range?.[1].format('YYYY-MM-DD'),
  })

  const stats = useMemo(() => (data ? buildDailyStats(data) : []), [data])

  const handleSearch = () => {
    setRange(
      pickerValue?.[0] && pickerValue?.[1]
        ? [pickerValue[0], pickerValue[1]]
        : null,
    )
  }

  const handleExport = () => {
    if (data) downloadCsv(`集合竞价统计_${dayjs().format('YYYYMMDD')}.csv`, statsToCsv(data, stats))
  }

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
      textStyle: { color: ChartColors.textMuted, fontSize: 10 },
      itemWidth: 14,
      itemHeight: 2,
      icon: 'rect',
    },
    grid: { left: 60, right: 30, top: 30, bottom: 70 },
    xAxis: {
      type: 'category',
      data: (data?.dates ?? []).map(formatDateLabel),
      axisLabel: { color: ChartColors.textMuted, fontSize: 10, rotate: 45 },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: ChartColors.panelBorder } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      name: '亿元',
      nameTextStyle: { color: ChartColors.textMuted, fontSize: 10 },
      axisLabel: { color: ChartColors.textMuted, fontSize: 10 },
      splitLine: { lineStyle: { color: ChartColors.grid } },
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
        <div className="flex items-center gap-2">
          <RangePicker
            value={pickerValue}
            onChange={(dates) => setPickerValue(dates)}
            presets={TRADING_DAY_PRESETS.map((p) => ({
              label: p.label,
              value: presetToRange(p.value),
            }))}
            placeholder={['开始日期', '结束日期']}
            size="small"
            allowClear
          />
          <Button size="small" type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            查询
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            disabled={!data || data.dates.length === 0}
            onClick={handleExport}
          >
            导出 CSV
          </Button>
        </div>
      </div>

      {isLoading ? (
        <Card variant="borderless">
          <div className="flex justify-center py-24">
            <Spin />
          </div>
        </Card>
      ) : error || !data || data.dates.length === 0 ? (
        <Card variant="borderless">
          <Empty
            className="py-16"
            description="暂无集合竞价数据（指数竞价采集任务交易日 9:26~9:29 运行后可用）"
          />
        </Card>
      ) : (
        <>
          <AuctionStatsCards stats={stats} />

          <Card
            variant="borderless"
            title="指数集合竞价成交额"
            extra={
              <span className="text-xs text-gray-400">
                单位：亿元 · 按 9:25 撮合口径按日统计
              </span>
            }
          >
            <ReactECharts option={option} style={{ height: '440px', width: '100%' }} notMerge />
            <SourceNote>
              指数 9:25 集合竞价成交额由 tushare stk_auction 聚合成分股 9:25 撮合数据计算
            </SourceNote>
          </Card>

          <Card
            variant="borderless"
            title="各交易日竞价统计"
            extra={<span className="text-xs text-gray-400">量比 = 当日合计 / 前 5 日合计均值</span>}
          >
            <AuctionStatsTable
              seriesNames={data.series.map((s) => s.name)}
              stats={stats}
            />
          </Card>
        </>
      )}
    </div>
  )
}
