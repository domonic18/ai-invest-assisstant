import { useEffect, useMemo, useRef, useState } from 'react'

import type { StockKlineBar } from '@ai-invest/shared'

import { CHROME_HEIGHT } from '@/components/charts/stockChartView/StockChartView'

import { SectorKlineView } from './SectorKlineView'
import { DUAL_VIEW_WEIGHTS, MIN_CHART_HEIGHT } from './sectorChartConfig'

const TOOLBAR_HEIGHT = CHROME_HEIGHT + 2

/** 单图/双图偏好全局记忆（板块详情共用一份，不按板块隔离）。 */
const DUAL_STORAGE_KEY = 'ai-invest.sector-detail.dual'

interface SectorChartAreaProps {
  bars: StockKlineBar[]
  markers?: { date: string; label?: string }[]
  /** 容器总高（含工具栏）；双图时按权重切分。 */
  height?: number
}

export function SectorChartArea({ bars, markers, height = 640 }: SectorChartAreaProps) {
  const [dual, setDual] = useState(() => {
    try {
      return localStorage.getItem(DUAL_STORAGE_KEY) !== '0'
    } catch {
      return true
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(DUAL_STORAGE_KEY, dual ? '1' : '0')
    } catch {
      // ignore storage errors
    }
  }, [dual])

  const chartContainerRef = useRef<HTMLDivElement>(null)
  const [containerHeight, setContainerHeight] = useState(height)

  useEffect(() => {
    const el = chartContainerRef.current
    if (!el) return

    const updateHeight = () => setContainerHeight(el.clientHeight)
    updateHeight()

    let ro: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(updateHeight)
      ro.observe(el)
    } else {
      window.addEventListener('resize', updateHeight)
    }
    return () => {
      ro?.disconnect()
      window.removeEventListener('resize', updateHeight)
    }
  }, [])

  const views = useMemo(
    () =>
      dual
        ? [
            { id: 'daily', period: 'daily' as const, indicators: { macd: true } },
            { id: 'weekly', period: 'weekly' as const, indicators: {} },
          ]
        : [{ id: 'daily', period: 'daily' as const, indicators: { macd: true } }],
    [dual],
  )

  const viewHeights = useMemo(() => {
    if (views.length === 2) {
      return DUAL_VIEW_WEIGHTS.map(
        (w) => Math.max(MIN_CHART_HEIGHT, Math.floor(containerHeight * w) - TOOLBAR_HEIGHT),
      )
    }
    return [
      Math.max(MIN_CHART_HEIGHT, Math.floor(containerHeight / views.length) - TOOLBAR_HEIGHT),
    ]
  }, [containerHeight, views.length])

  const handleDualChange = (next: boolean) => setDual(next)

  return (
    <div ref={chartContainerRef} className="flex flex-col gap-2" style={{ height }}>
      {views.map((view, i) => (
        <SectorKlineView
          key={view.id}
          bars={bars}
          markers={markers}
          height={viewHeights[i] ?? MIN_CHART_HEIGHT}
          defaultPeriod={view.period}
          defaultIndicators={view.indicators}
          layoutToggle={
            i === 0 ? { value: dual, onChange: handleDualChange } : undefined
          }
        />
      ))}
    </div>
  )
}
