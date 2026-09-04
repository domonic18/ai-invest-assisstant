import ReactECharts from 'echarts-for-react'
import type { EChartsOption, SeriesOption } from 'echarts'
import { useMemo } from 'react'

import type { SectorFlowTrend } from '@/api/fundFlow'
import { useColorScheme } from '@/stores/settings'

// 只画累计 |净流入| 前 8 的板块，其余合并为「其他」
const TOP_SECTORS = 8

// 红涨绿跌 / 绿涨红跌两套色族：区间内累计净流入的板块用涨色族，净流出用跌色族
const RISE_FAMILY = {
  cn: ['#f85149', '#ff7b72', '#ffa198', '#d73a49', '#e5534b', '#ff9d94', '#c93c37', '#f47067'],
  us: ['#2ea043', '#3fb950', '#56d364', '#238636', '#2da44e', '#4ac26b', '#1a7f37', '#46c160'],
} as const
const FALL_FAMILY = {
  cn: ['#2ea043', '#3fb950', '#56d364', '#238636', '#2da44e', '#4ac26b', '#1a7f37', '#46c160'],
  us: ['#f85149', '#ff7b72', '#ffa198', '#d73a49', '#e5534b', '#ff9d94', '#c93c37', '#f47067'],
} as const

interface SectorFlowAreaChartProps {
  data: SectorFlowTrend
  selectedDate: string | null
  onSelectDate: (date: string) => void
}

export function SectorFlowAreaChart({
  data,
  selectedDate,
  onSelectDate,
}: SectorFlowAreaChartProps) {
  const scheme = useColorScheme()

  const series = useMemo(() => {
    const ranked = data.sectors
      .map((s) => ({
        ...s,
        absTotal: s.values.reduce<number>((acc, v) => acc + Math.abs(v ?? 0), 0),
        netTotal: s.values.reduce<number>((acc, v) => acc + (v ?? 0), 0),
      }))
      .sort((a, b) => b.absTotal - a.absTotal)
    const top = ranked.slice(0, TOP_SECTORS)

    const riseColors = RISE_FAMILY[scheme]
    const fallColors = FALL_FAMILY[scheme]
    let riseIdx = 0
    let fallIdx = 0

    const list: SeriesOption[] = top.map((sector) => {
      const isRise = sector.netTotal >= 0
      const color = isRise
        ? riseColors[riseIdx++ % riseColors.length]
        : fallColors[fallIdx++ % fallColors.length]
      return {
        name: sector.name,
        type: 'line',
        stack: 'flow',
        stackStrategy: 'samesign',
        smooth: true,
        symbol: 'none',
        color,
        lineStyle: { width: 1 },
        areaStyle: { opacity: 0.75 },
        emphasis: { focus: 'series' },
        data: sector.values.map((v) => v ?? 0),
      }
    })

    // 选中天的竖线标记（与排名图 timeline 联动）
    if (list.length > 0 && selectedDate) {
      list[0] = {
        ...list[0],
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: '#8c8c8c', type: 'dashed', width: 1 },
          data: [{ xAxis: selectedDate }],
        },
      }
    }
    return list
  }, [data, scheme, selectedDate])

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
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
    grid: { left: 60, right: 30, top: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: data.dates,
      boundaryGap: false,
      axisLabel: {
        color: '#8c8c8c',
        fontSize: 10,
        formatter: (value: string) => value.slice(5),
      },
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
    series,
  }

  return (
    <ReactECharts
      option={option}
      style={{ height: '360px', width: '100%' }}
      notMerge
      onEvents={{
        click: (params: { componentType?: string; name?: string }) => {
          if (params.componentType === 'series' && params.name) {
            onSelectDate(params.name)
          }
        },
      }}
    />
  )
}
