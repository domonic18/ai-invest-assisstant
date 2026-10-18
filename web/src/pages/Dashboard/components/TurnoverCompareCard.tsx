import { Card, Skeleton } from 'antd'

import type { EChartsOption } from 'echarts'

import type { TurnoverCompare, TurnoverComparePoint } from '@ai-invest/shared'
import ReactECharts from '@/components/charts/ReactECharts'
import { SourceNote } from '@/components/common/SourceNote'
import { useTurnoverCompare } from '@/hooks/useMarket'
import { useColorScheme } from '@/stores/settings'
import { changeHex, fallHex, riseHex } from '@/utils/formatters'

interface TurnoverCompareCardProps {
  /** 指定复盘日期时不轮询；实时日（未指定）每分钟刷新跟随采集节奏。 */
  tradeDate?: string
}

const TODAY_COLOR = '#4d8ef7'
const PREV_COLOR = '#d29922'
const FORECAST_COLOR = '#f472b6'

function StatCell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <div className="text-lg font-semibold font-mono" style={{ color: color ?? '#e6e6e6' }}>
        {value}
      </div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  )
}

function fmtYi(value: number | null | undefined, signed = false): string {
  if (value == null) return '-'
  const sign = signed && value > 0 ? '+' : ''
  return `${sign}${value.toFixed(0)}亿`
}

function buildOption(data: TurnoverCompare, diffColor: (v: number) => string): EChartsOption {
  const points: TurnoverComparePoint[] = data.points
  const times = points.map((p) => p.time)
  const today = points.map((p) => p.today)
  const prev = points.map((p) => p.prev)
  const diff = points.map((p) => ({
    value: p.diff,
    itemStyle: { color: diffColor(p.diff) },
  }))
  const forecast = data.forecastAmount

  const tooltipFormatter = (params: unknown): string => {
    const items = Array.isArray(params) ? params : [params]
    const idx = (items[0] as { dataIndex?: number })?.dataIndex ?? 0
    const p = points[idx]
    if (!p) return ''
    return [
      p.time,
      `当日累计 ${fmtYi(p.today)}`,
      `昨日同期 ${fmtYi(p.prev)}`,
      `较昨日 ${fmtYi(p.diff, true)}`,
    ].join('<br/>')
  }

  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: tooltipFormatter,
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 16,
      textStyle: { color: '#8c8c8c', fontSize: 11 },
      data: ['当日累计', '昨日同期'],
    },
    grid: [
      { left: 56, right: 8, top: 26, height: '56%' },
      { left: 56, right: 8, top: '74%', height: '20%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: times,
        boundaryGap: false,
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#3a3f4b' } },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: times,
        boundaryGap: true,
        axisLabel: { color: '#8c8c8c', fontSize: 10, interval: Math.ceil(times.length / 6) },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#3a3f4b' } },
      },
    ],
    yAxis: [
      {
        scale: true,
        axisLabel: {
          color: '#8c8c8c',
          fontSize: 10,
          formatter: (value: number) => `${value.toFixed(0)}亿`,
        },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      },
      {
        gridIndex: 1,
        axisLabel: {
          color: '#8c8c8c',
          fontSize: 10,
          formatter: (value: number) => `${value.toFixed(0)}`,
        },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '当日累计',
        type: 'line',
        data: today,
        showSymbol: false,
        lineStyle: { color: TODAY_COLOR, width: 1.5 },
        itemStyle: { color: TODAY_COLOR },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${TODAY_COLOR}2e` },
              { offset: 1, color: `${TODAY_COLOR}00` },
            ],
          },
        },
        markLine: forecast
          ? {
              silent: true,
              symbol: 'none',
              data: [{ yAxis: forecast }],
              lineStyle: { color: FORECAST_COLOR, type: 'dashed', width: 1 },
              label: {
                color: FORECAST_COLOR,
                fontSize: 10,
                formatter: `预测全天 ${fmtYi(forecast)}`,
                position: 'insideEndTop',
              },
            }
          : undefined,
      },
      {
        name: '昨日同期',
        type: 'line',
        data: prev,
        showSymbol: false,
        lineStyle: { color: PREV_COLOR, width: 1.2, type: 'dashed' },
        itemStyle: { color: PREV_COLOR },
      },
      {
        name: '较昨日增减',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: diff,
        barWidth: '60%',
      },
    ],
  }
}

/** 两市量能对比卡（诊大盘「市场成交额」版式）：累计成交额双曲线 + 较昨日增减副图。 */
export function TurnoverCompareCard({ tradeDate }: TurnoverCompareCardProps) {
  useColorScheme()
  const { data, isLoading } = useTurnoverCompare(tradeDate)

  if (isLoading) {
    return <Skeleton active paragraph={{ rows: 6 }} />
  }
  if (!data || data.points.length === 0) {
    return (
      <Card variant="borderless" title="两市量能对比">
        <div className="text-gray-500 text-sm py-6 text-center">
          该日无量能对比数据（非交易日或分钟线未采集）
        </div>
      </Card>
    )
  }

  const last = data.points[data.points.length - 1]

  return (
    <Card
      variant="borderless"
      title="两市量能对比"
      extra={
        <span className="text-xs text-gray-500">
          数据日期 {data.tradeDate} · 对比 {data.prevTradeDate ?? '-'}
        </span>
      }
    >
      <div className="grid grid-cols-4 gap-2 mb-4">
        <StatCell label="当日累计" value={fmtYi(data.todayAmount)} />
        <StatCell label="预测全天" value={fmtYi(data.forecastAmount)} color={FORECAST_COLOR} />
        <StatCell label="昨日全天" value={fmtYi(data.prevAmount)} color={PREV_COLOR} />
        <StatCell
          label="较昨日增减"
          value={fmtYi(last.diff, true)}
          color={changeHex(last.diff)}
        />
      </div>
      <ReactECharts
        option={buildOption(data, (v) => (v >= 0 ? riseHex() : fallHex()))}
        style={{ height: '300px', width: '100%' }}
        notMerge
      />
      <SourceNote>
        口径：上证指数 + 深证综指分钟累计成交额（与交易所官方总额误差 &lt;0.1%）·
        分钟线来自新浪财经 · 预测全天 = 昨日总额 × 当日/昨日同期累计比 · 盘中每分钟更新
      </SourceNote>
    </Card>
  )
}
