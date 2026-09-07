import { useEffect, useMemo, useRef, useState } from 'react'

import { StockChartView } from '@/components/charts/stockChartView'

import {
  buildViews,
  type ChartViewConfig,
  DEFAULT_INDICATORS,
  MIN_CHART_HEIGHT,
  STORAGE_KEY,
  TOOLBAR_HEIGHT,
} from '../chartConfig'

/** 双图加权分配：上 58 / 下 42，与原型一致。 */
const DUAL_VIEW_WEIGHTS = [0.58, 0.42]

function normalizeViews(parsed: unknown): ChartViewConfig[] | null {
  if (!Array.isArray(parsed) || parsed.length === 0) return null
  return (parsed as ChartViewConfig[]).map((v) => ({
    ...v,
    indicators: { ...DEFAULT_INDICATORS, ...v.indicators },
  }))
}

interface StockChartAreaProps {
  stockCode: string
}

export function StockChartArea({ stockCode }: StockChartAreaProps) {
  const [views, setViews] = useState<ChartViewConfig[]>(() => buildViews(true))
  const [dual, setDual] = useState(true)
  const [viewsLoaded, setViewsLoaded] = useState(false)

  const storageKey = useMemo(() => `${STORAGE_KEY}.${stockCode}`, [stockCode])

  useEffect(() => {
    if (!stockCode) return
    try {
      const rawViews = localStorage.getItem(storageKey)
      const rawDual = localStorage.getItem(`${storageKey}.dual`)
      const nextDual = rawDual !== '0'
      const parsed = rawViews ? normalizeViews(JSON.parse(rawViews)) : null
      setDual(nextDual)
      setViews(parsed ?? buildViews(nextDual))
    } catch {
      setDual(true)
      setViews(buildViews(true))
    }
    setViewsLoaded(true)
  }, [storageKey, stockCode])

  useEffect(() => {
    if (!viewsLoaded) return
    try {
      localStorage.setItem(storageKey, JSON.stringify(views))
      localStorage.setItem(`${storageKey}.dual`, dual ? '1' : '0')
    } catch {
      // ignore storage errors
    }
  }, [views, dual, viewsLoaded, storageKey])

  const handleDualChange = (next: boolean) => {
    setDual(next)
    setViews((prev) => {
      if (next) {
        if (prev.length === 2) return prev
        const weekly = buildViews(true).find((v) => v.id === 'weekly')
        return weekly ? [...prev, { ...weekly }] : prev
      }
      return prev.filter((v) => v.id === 'daily')
    })
  }

  const updateView = (id: string, patch: Partial<ChartViewConfig>) => {
    setViews((prev) => prev.map((v) => (v.id === id ? { ...v, ...patch } : v)))
  }

  const chartContainerRef = useRef<HTMLDivElement>(null)
  const [containerHeight, setContainerHeight] = useState(600)

  useEffect(() => {
    const el = chartContainerRef.current
    if (!el) return

    const updateHeight = () => {
      setContainerHeight(el.clientHeight)
    }
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

  const viewHeights = useMemo(() => {
    if (views.length === 2) {
      return DUAL_VIEW_WEIGHTS.map(
        (w) => Math.max(MIN_CHART_HEIGHT, Math.floor(containerHeight * w) - TOOLBAR_HEIGHT),
      )
    }
    const each = Math.max(
      MIN_CHART_HEIGHT,
      Math.floor(containerHeight / views.length) - TOOLBAR_HEIGHT,
    )
    return Array.from({ length: views.length }, () => each)
  }, [containerHeight, views.length])

  return (
    <div
      ref={chartContainerRef}
      className="flex-1 overflow-hidden flex flex-col"
      style={{ backgroundColor: '#050608' }}
    >
      {views.map((view, i) => (
        <StockChartView
          key={view.id}
          code={stockCode}
          defaultPeriod={view.period}
          defaultIndicators={view.indicators}
          onPeriodChange={(period) => updateView(view.id, { period })}
          onIndicatorsChange={(indicators) => updateView(view.id, { indicators })}
          height={viewHeights[i] ?? MIN_CHART_HEIGHT}
          layoutToggle={i === 0 ? { value: dual, onChange: handleDualChange } : undefined}
        />
      ))}
    </div>
  )
}
