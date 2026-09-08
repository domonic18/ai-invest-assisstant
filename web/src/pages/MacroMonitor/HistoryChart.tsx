import { Card, Empty, Spin } from 'antd'
import dayjs from 'dayjs'
import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'

import { useCalendarEvents } from '@/hooks/useCalendarEvents'
import { useGlobalIndexHistory, useIndexKline } from '@/hooks/useMarket'
import { ChartColors } from '@/theme/colors'

interface HistoryChartProps {
  /** A 股指数（sh/sz 前缀）走指数日 K；其余走全球指标历史（含 US2Y10S 衍生）。 */
  code: string
  name: string
  /** y 轴/tooltip 单位后缀（% / bp / 空）。 */
  unit?: string
  decimals?: number
}

const MONTHS = 12

export function HistoryChart({ code, name, unit = '', decimals = 2 }: HistoryChartProps) {
  const isAshare = /^(sh|sz)/.test(code)
  const kline = useIndexKline(code, 'daily', isAshare)
  const globalHistory = useGlobalIndexHistory(code, MONTHS, !isAshare)
  const loading = isAshare ? kline.isLoading : globalHistory.isLoading

  const dates: string[] = useMemo(() => {
    if (isAshare) {
      return (kline.data?.bars ?? []).map((b) => b.date)
    }
    return (globalHistory.data ?? []).map((p) => p.tradeDate)
  }, [isAshare, kline.data, globalHistory.data])

  const values: (number | null)[] = useMemo(() => {
    if (isAshare) {
      return (kline.data?.bars ?? []).map((b) => b.close)
    }
    return (globalHistory.data ?? []).map((p) => p.close)
  }, [isAshare, kline.data, globalHistory.data])

  // FOMC 会议竖线标注（近 12 个月日历事件中标题含 FOMC 的会议日）
  const rangeStart = useMemo(
    () => dayjs().subtract(MONTHS, 'month').format('YYYY-MM-DD'),
    [],
  )
  const { data: calendarEvents } = useCalendarEvents(rangeStart, dayjs().format('YYYY-MM-DD'))
  const fomcMarks = useMemo(() => {
    const fDates = (calendarEvents ?? [])
      .filter((e) => /fomc/i.test(e.title))
      .map((e) => e.eventTime.slice(0, 10))
      .filter((d) => d >= (dates[0] ?? d))
    // category 轴 markLine 需命中轴数据：取该会议日后首个交易日
    return fDates
      .map((d) => dates.find((td) => td >= d))
      .filter((d): d is string => Boolean(d))
  }, [calendarEvents, dates])

  if (loading) {
    return (
      <Card variant="borderless">
        <div className="flex justify-center py-16">
          <Spin />
        </div>
      </Card>
    )
  }

  if (dates.length === 0) {
    return (
      <Card variant="borderless">
        <Empty className="py-12" description="该指标暂无历史数据（采集任务运行后自动积累）" />
      </Card>
    )
  }

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'line' as const },
      valueFormatter: (value: unknown) =>
        typeof value === 'number' ? `${value.toFixed(decimals)}${unit}` : '-',
    },
    grid: { left: 60, right: 40, top: 30, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: dates,
      boundaryGap: false,
      axisLabel: {
        color: ChartColors.textMuted,
        fontSize: 10,
        formatter: (value: string) => value.slice(2, 7),
      },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: ChartColors.panelBorder } },
    },
    yAxis: {
      type: 'value' as const,
      scale: true,
      axisLabel: { color: ChartColors.textMuted, fontSize: 10 },
      splitLine: { lineStyle: { color: ChartColors.grid } },
    },
    series: [
      {
        name,
        type: 'line' as const,
        smooth: true,
        symbol: 'none',
        color: '#58a6ff',
        lineStyle: { width: 2 },
        data: values,
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: ChartColors.textMuted, type: 'dashed', width: 1 },
          data: fomcMarks.map((d) => ({ xAxis: d })),
        },
        // 末点数值标注
        markPoint: {
          symbol: 'circle',
          symbolSize: 5,
          label: {
            show: true,
            position: 'left',
            color: '#58a6ff',
            fontSize: 11,
            fontWeight: 600,
            formatter: () =>
              `${(values[values.length - 1] ?? 0).toFixed(decimals)}${unit}`,
          },
          data:
            values[values.length - 1] === null
              ? []
              : [{ coord: [dates[dates.length - 1], values[values.length - 1]] }],
        },
      },
    ],
  }

  return (
    <Card
      variant="borderless"
      title={`${name} · 近 ${MONTHS} 个月走势${unit ? `（${unit}）` : ''}`}
      extra={
        <span className="text-xs text-gray-600">虚线标注 = FOMC 议息会议</span>
      }
    >
      <ReactECharts option={option} style={{ height: '300px', width: '100%' }} notMerge />
    </Card>
  )
}
