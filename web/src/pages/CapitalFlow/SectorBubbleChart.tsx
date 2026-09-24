import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useMemo } from 'react'

import type { SectorQuoteItem, SectorQuoteResponse } from '@ai-invest/shared'

import { useColorScheme } from '@/stores/settings'
import { ChartColors } from '@/theme/colors'
import { fallHex, formatAmount, riseHex } from '@/utils/formatters'

/** 入选板块数（按成交额取 top N，保证气泡平铺不重叠）。 */
const TOP_N = 20
/** 上涨/下跌泳道的纵坐标（固定档位，位置只表达方向，大小表达涨跌幅）。 */
const RISE_LANE = 1
const FALL_LANE = -1

type Quote = SectorQuoteItem & { changePct: number }

export function SectorBubbleChart({ data }: { data: SectorQuoteResponse }) {
  useColorScheme()

  const option = useMemo(() => {
    const items: Quote[] = data.items.filter(
      (it): it is Quote => it.changePct !== null,
    )
    const selected = [...items]
      .sort((a, b) => (b.amount ?? 0) - (a.amount ?? 0))
      .slice(0, TOP_N)
    const rises = selected
      .filter((it) => it.changePct >= 0)
      .sort((a, b) => b.changePct - a.changePct)
    const falls = selected
      .filter((it) => it.changePct < 0)
      .sort((a, b) => a.changePct - b.changePct)
    const ordered = [...rises, ...falls]

    const maxAbs = Math.max(
      ...ordered.map((it) => Math.abs(it.changePct)),
      0.01,
    )

    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 16, right: 16, top: 40, bottom: 40 },
      tooltip: {
        trigger: 'item',
        formatter: (params: { dataIndex: number }) => {
          const it = ordered[params.dataIndex]
          return (
            `${it.sectorName}<br/>` +
            `涨跌幅：<b>${it.changePct >= 0 ? '+' : ''}${it.changePct.toFixed(2)}%</b><br/>` +
            `成交额：${formatAmount(it.amount)}`
          )
        },
      },
      xAxis: {
        type: 'category',
        data: ordered.map((it) => it.sectorName),
        show: false,
      },
      yAxis: {
        type: 'value',
        min: -2.4,
        max: 2.4,
        show: false,
      },
      series: [
        {
          type: 'scatter',
          data: ordered.map((it) => ({
            value: [it.sectorName, it.changePct >= 0 ? RISE_LANE : FALL_LANE],
            symbolSize: 14 + (Math.abs(it.changePct) / maxAbs) * 30,
            itemStyle: {
              color: it.changePct >= 0 ? riseHex() : fallHex(),
              opacity: 0.75,
            },
            label: {
              show: true,
              formatter: `${it.sectorName}\n${it.changePct >= 0 ? '+' : ''}${it.changePct.toFixed(2)}%`,
              position: it.changePct >= 0 ? ('top' as const) : ('bottom' as const),
              fontSize: 10,
              lineHeight: 14,
              color: ChartColors.textMuted,
            },
          })),
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: ChartColors.textMuted, width: 1 },
            data: [{ yAxis: 0 }],
          },
        },
      ],
    }
  }, [data])

  return (
    <ReactECharts
      option={option as unknown as EChartsOption}
      style={{ height: '320px', width: '100%' }}
      notMerge
    />
  )
}
