import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useMemo } from 'react'

import type { SectorFlowTrend } from '@/api/fundFlow'
import { ChartColors } from '@/theme/colors'
import { fallHex, riseHex } from '@/utils/formatters'
import { useColorScheme } from '@/stores/settings'

// 每天左榜展示净流入前 10（涨色）、右榜净流出前 10（跌色），对齐原型双栏排行
const TOP_N = 10

// 应用主色（Linear 靛蓝），时间轴选中点与播放控件用它与涨跌色区分
const ACCENT = '#5e6ad2'

interface SectorRankBarChartProps {
  data: SectorFlowTrend
  selectedDate: string | null
  onSelectDate: (date: string) => void
}

interface RankItem {
  name: string
  value: number
}

function pickInflow(data: SectorFlowTrend, dateIndex: number): RankItem[] {
  return data.sectors
    .map((s) => ({ name: s.name, value: s.values[dateIndex] }))
    .filter((it): it is RankItem => it.value !== null && it.value !== undefined)
    .filter((it) => it.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, TOP_N)
}

function pickOutflow(data: SectorFlowTrend, dateIndex: number): RankItem[] {
  return data.sectors
    .map((s) => ({ name: s.name, value: s.values[dateIndex] }))
    .filter((it): it is RankItem => it.value !== null && it.value !== undefined)
    .filter((it) => it.value < 0)
    .sort((a, b) => a.value - b.value)
    .slice(0, TOP_N)
}

export function SectorRankBarChart({
  data,
  selectedDate,
  onSelectDate,
}: SectorRankBarChartProps) {
  useColorScheme()
  const currentIndex = useMemo(() => {
    const idx = selectedDate ? data.dates.indexOf(selectedDate) : -1
    return idx >= 0 ? idx : Math.max(data.dates.length - 1, 0)
  }, [data.dates, selectedDate])

  const muted = ChartColors.textMuted
  const axisValue = {
    type: 'value' as const,
    name: '亿元',
    nameTextStyle: { color: muted, fontSize: 10 },
    axisLabel: { color: muted, fontSize: 10 },
    splitLine: { lineStyle: { color: ChartColors.grid } },
  }
  const axisCategory = {
    type: 'category' as const,
    inverse: true,
    axisLabel: { color: muted, fontSize: 10 },
    axisTick: { show: false },
    axisLine: { lineStyle: { color: ChartColors.panelBorder } },
  }

  const option = {
    baseOption: {
      backgroundColor: 'transparent',
      animation: false,
      title: [
        {
          text: `净流入 TOP${TOP_N}`,
          left: '25%',
          top: 0,
          textAlign: 'center',
          textStyle: { color: riseHex(), fontSize: 12, fontWeight: 600 },
        },
        {
          text: `净流出 TOP${TOP_N}`,
          left: '75%',
          top: 0,
          textAlign: 'center',
          textStyle: { color: fallHex(), fontSize: 12, fontWeight: 600 },
        },
      ],
      timeline: {
        axisType: 'category',
        data: data.dates,
        currentIndex,
        autoPlay: false,
        playInterval: 1200,
        bottom: 0,
        label: {
          color: muted,
          fontSize: 10,
          formatter: (value: string) => value.slice(5),
        },
        lineStyle: { color: ChartColors.panelBorder },
        itemStyle: { color: ChartColors.panelBorder },
        checkpointStyle: { color: ACCENT, borderColor: ACCENT },
        controlStyle: { color: muted, borderColor: muted },
        emphasis: { label: { color: ChartColors.textMain } },
      },
      grid: [
        { left: 90, right: '55%', top: 30, bottom: 60 },
        { left: '55%', right: 90, top: 30, bottom: 60 },
      ],
      xAxis: [
        {
          ...axisValue,
          gridIndex: 0,
          // 端点金额标签留 15% 余量防溢出
          max: (v: { max: number }) => Math.ceil(v.max * 1.15),
        },
        {
          ...axisValue,
          gridIndex: 1,
          min: (v: { min: number }) => Math.floor(v.min * 1.15),
        },
      ],
      yAxis: [
        { ...axisCategory, gridIndex: 0 },
        { ...axisCategory, gridIndex: 1 },
      ],
      tooltip: {
        trigger: 'item',
        formatter: (params: { name: string; value: number }) =>
          `${params.name}: <b>${params.value.toFixed(2)} 亿</b>`,
      },
      series: [
        {
          type: 'bar',
          xAxisIndex: 0,
          yAxisIndex: 0,
          barMaxWidth: 14,
          label: { show: true, fontSize: 10, color: muted },
        },
        {
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          barMaxWidth: 14,
          label: { show: true, fontSize: 10, color: muted },
        },
      ],
    },
    options: data.dates.map((_, dateIndex) => {
      const inflow = pickInflow(data, dateIndex)
      const outflow = pickOutflow(data, dateIndex)
      return {
        yAxis: [
          { data: inflow.map((it) => it.name) },
          { data: outflow.map((it) => it.name) },
        ],
        series: [
          {
            data: inflow.map((it) => ({
              value: it.value,
              itemStyle: { color: riseHex() },
              label: { position: 'right' as const, formatter: `${it.value.toFixed(2)} 亿` },
            })),
          },
          {
            data: outflow.map((it) => ({
              value: it.value,
              itemStyle: { color: fallHex() },
              label: { position: 'left' as const, formatter: `${it.value.toFixed(2)} 亿` },
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
