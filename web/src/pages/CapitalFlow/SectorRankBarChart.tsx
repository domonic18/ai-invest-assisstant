import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useMemo } from 'react'

import type { SectorFlowTrend } from '@/api/fundFlow'
import { changeHex } from '@/utils/formatters'

// 每天展示净流入前 10 + 净流出前 10
const TOP_N = 10

interface SectorRankBarChartProps {
  data: SectorFlowTrend
  selectedDate: string | null
  onSelectDate: (date: string) => void
}

interface RankItem {
  name: string
  value: number
}

function pickDayItems(data: SectorFlowTrend, dateIndex: number): RankItem[] {
  const items: RankItem[] = data.sectors
    .map((s) => ({ name: s.name, value: s.values[dateIndex] }))
    .filter((it): it is RankItem => it.value !== null && it.value !== undefined)
    .sort((a, b) => b.value - a.value)
  if (items.length <= TOP_N * 2) return items
  return [...items.slice(0, TOP_N), ...items.slice(-TOP_N)].sort(
    (a, b) => b.value - a.value,
  )
}

export function SectorRankBarChart({
  data,
  selectedDate,
  onSelectDate,
}: SectorRankBarChartProps) {
  const currentIndex = useMemo(() => {
    const idx = selectedDate ? data.dates.indexOf(selectedDate) : -1
    return idx >= 0 ? idx : Math.max(data.dates.length - 1, 0)
  }, [data.dates, selectedDate])

  const option = {
    baseOption: {
      backgroundColor: 'transparent',
      animation: false,
      timeline: {
        axisType: 'category',
        data: data.dates,
        currentIndex,
        autoPlay: false,
        playInterval: 1200,
        bottom: 0,
        label: {
          color: '#8c8c8c',
          fontSize: 10,
          formatter: (value: string) => value.slice(5),
        },
        lineStyle: { color: '#3a3f4b' },
        itemStyle: { color: '#3a3f4b' },
        checkpointStyle: { color: '#5470c6', borderColor: '#5470c6' },
        controlStyle: { color: '#8c8c8c', borderColor: '#8c8c8c' },
        emphasis: { label: { color: '#c9cdd4' } },
      },
      grid: { left: 90, right: 70, top: 10, bottom: 60 },
      xAxis: {
        type: 'value',
        // 两侧留 25% 余量，防止长条的端点金额标签溢出到坐标轴区域
        min: (v: { min: number }) => Math.floor(v.min * 1.25),
        max: (v: { max: number }) => Math.ceil(v.max * 1.25),
        name: '亿元',
        nameTextStyle: { color: '#8c8c8c', fontSize: 10 },
        axisLabel: { color: '#8c8c8c', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        axisLabel: { color: '#8c8c8c', fontSize: 10 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#3a3f4b' } },
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: { name: string; value: number }) =>
          `${params.name}: <b>${params.value.toFixed(2)} 亿</b>`,
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 14,
          label: { show: true, fontSize: 10, color: '#8c8c8c' },
        },
      ],
    },
    options: data.dates.map((_, dateIndex) => {
      const items = pickDayItems(data, dateIndex)
      return {
        yAxis: { data: items.map((it) => it.name) },
        series: [
          {
            data: items.map((it) => ({
              value: it.value,
              itemStyle: { color: changeHex(it.value) },
              label: {
                position: it.value >= 0 ? ('right' as const) : ('left' as const),
                formatter: `${it.value.toFixed(2)} 亿`,
              },
            })),
          },
        ],
      }
    }),
  }

  return (
    <ReactECharts
      option={option as unknown as EChartsOption}
      style={{ height: '520px', width: '100%' }}
      notMerge
      onEvents={{
        timelinechanged: (params: { currentIndex: number }) => {
          const day = data.dates[params.currentIndex]
          if (day) onSelectDate(day)
        },
      }}
    />
  )
}
