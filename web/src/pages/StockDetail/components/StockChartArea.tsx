import { useEffect, useMemo, useRef, useState } from 'react'

import { StockChartView } from '@/components/charts/stockChartView'
import { usePaperTradeTradeMarkers } from '@/hooks/usePaperTrade'
import { useIsNarrowScreen } from '@/hooks/useIsNarrowScreen'
import { useKlineViewLayoutStore } from '@/stores/klineViewLayout'

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

/**
 * 视图清单与布局对齐：单图只留 daily，双图补齐 weekly；
 * 周期优先取会话 store（切股继承上次调整），store 未记录时回退到各股持久化值。
 */
function reconcileViews(
  views: ChartViewConfig[],
  dual: boolean,
  layoutPeriods: Record<string, string>,
): ChartViewConfig[] {
  let next = views.map((v) =>
    layoutPeriods[v.id] && layoutPeriods[v.id] !== v.period
      ? { ...v, period: layoutPeriods[v.id] }
      : v,
  )
  if (!dual) return next.filter((v) => v.id === 'daily')
  if (next.length === 1) {
    const weekly = buildViews(true).find((v) => v.id === 'weekly')
    if (weekly) {
      const period = layoutPeriods[weekly.id] ?? weekly.period
      next = [...next, { ...weekly, period }]
    }
  }
  return next
}

interface StockChartAreaProps {
  stockCode: string
}

export function StockChartArea({ stockCode }: StockChartAreaProps) {
  // 单/双图与各视图周期是跨股票的会话级布局（切股继承），存 klineViewLayout store；
  // 双图不落盘（持久化会把用户锁在双图），指标等偏好仍按股持久化
  const [views, setViews] = useState<ChartViewConfig[]>(() => buildViews(false))
  const dual = useKlineViewLayoutStore((s) => s.dual)
  const setDual = useKlineViewLayoutStore((s) => s.setDual)
  const layoutPeriods = useKlineViewLayoutStore((s) => s.periods)
  const setLayoutPeriod = useKlineViewLayoutStore((s) => s.setPeriod)
  const [viewsLoaded, setViewsLoaded] = useState(false)

  // 模拟盘成交回报 → 图表 B/S/T 标记（未登录/无成交为空数组，不影响图表）
  const markersQuery = usePaperTradeTradeMarkers(
    /^\d{6}$/.test(stockCode) ? stockCode : undefined,
  )
  const tradeMarks = useMemo(() => markersQuery.data?.items ?? [], [markersQuery.data])

  const storageKey = useMemo(() => `${STORAGE_KEY}.${stockCode}`, [stockCode])

  // 窄屏强制单图：双图上下叠每张仅 ~150px 高不可用；双图偏好保留，桌面端仍生效
  const isNarrow = useIsNarrowScreen()
  const effectiveDual = dual && !isNarrow
  const visibleViews = useMemo(
    () => (effectiveDual ? views : views.filter((v) => v.id === 'daily')),
    [views, effectiveDual],
  )

  useEffect(() => {
    if (!stockCode) return
    // 切股只换数据源：布局（dual）与周期从会话 store 继承，不再重置回单图
    const layout = useKlineViewLayoutStore.getState()
    try {
      const rawViews = localStorage.getItem(storageKey)
      const parsed = rawViews ? normalizeViews(JSON.parse(rawViews)) : null
      setViews(reconcileViews(parsed ?? buildViews(false), layout.dual, layout.periods))
    } catch {
      setViews(reconcileViews(buildViews(false), layout.dual, layout.periods))
    }
    setViewsLoaded(true)
  }, [storageKey, stockCode])

  useEffect(() => {
    if (!viewsLoaded) return
    try {
      localStorage.setItem(storageKey, JSON.stringify(views))
    } catch {
      // ignore storage errors
    }
  }, [views, viewsLoaded, storageKey])

  const handleDualChange = (next: boolean) => {
    setDual(next)
    setViews((prev) =>
      reconcileViews(prev, next, useKlineViewLayoutStore.getState().periods),
    )
  }

  const updateView = (id: string, patch: Partial<ChartViewConfig>) => {
    setViews((prev) => prev.map((v) => (v.id === id ? { ...v, ...patch } : v)))
  }

  const handlePeriodChange = (viewId: string, period: string) => {
    // 周期写入会话 store（切股继承）+ per-stock 持久化（新会话回退值）
    setLayoutPeriod(viewId, period)
    updateView(viewId, { period })
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
    // 窄屏工具栏换行为两行（~56px），预留高度相应加大防 x 轴被裁
    const toolbarH = isNarrow ? 60 : TOOLBAR_HEIGHT
    if (visibleViews.length === 2) {
      return DUAL_VIEW_WEIGHTS.map(
        (w) => Math.max(MIN_CHART_HEIGHT, Math.floor(containerHeight * w) - toolbarH),
      )
    }
    const each = Math.max(
      MIN_CHART_HEIGHT,
      Math.floor(containerHeight / visibleViews.length) - toolbarH,
    )
    return Array.from({ length: visibleViews.length }, () => each)
  }, [containerHeight, visibleViews.length, isNarrow])

  return (
    <div
      ref={chartContainerRef}
      className="flex-1 overflow-hidden flex flex-col"
      style={{ backgroundColor: '#050608' }}
    >
      {visibleViews.map((view, i) => (
        <StockChartView
          key={view.id}
          viewId={view.id}
          code={stockCode}
          defaultPeriod={layoutPeriods[view.id] ?? view.period}
          defaultIndicators={view.indicators}
          onPeriodChange={(period) => handlePeriodChange(view.id, period)}
          onIndicatorsChange={(indicators) => updateView(view.id, { indicators })}
          height={viewHeights[i] ?? MIN_CHART_HEIGHT}
          layoutToggle={i === 0 ? { value: effectiveDual, onChange: handleDualChange } : undefined}
          tradeMarks={tradeMarks}
        />
      ))}
    </div>
  )
}
