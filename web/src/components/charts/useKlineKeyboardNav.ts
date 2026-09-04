import { useCallback, useEffect, useRef } from 'react'
import type ReactECharts from 'echarts-for-react'

interface ZoomWindow {
  start: number
  end: number
}

interface AxisPointerEvent {
  axesInfo?: Array<{ value?: number | string }>
}

interface DataZoomOptionEntry {
  start?: number
  end?: number
  startValue?: number | string
  endValue?: number | string
}

const MIN_SPAN = 5
const ZOOM_IN_FACTOR = 0.8
const ZOOM_OUT_FACTOR = 1 / ZOOM_IN_FACTOR

/**
 * K 线键盘导航（对标同花顺）：鼠标悬浮图表时，
 * ↑/↓ 以十字光标为锚缩放可见区间（无光标时锚定右端最新数据），←/→ 左右平移。
 */
export function useKlineKeyboardNav(barCount: number) {
  const chartRef = useRef<ReactECharts | null>(null)
  const windowRef = useRef<ZoomWindow | null>(null)
  const anchorRef = useRef<number | null>(null)
  const hoverRef = useRef(false)
  const barCountRef = useRef(barCount)
  barCountRef.current = barCount

  useEffect(() => {
    windowRef.current = null
    anchorRef.current = null
  }, [barCount])

  const syncWindow = useCallback(() => {
    const chart = chartRef.current?.getEchartsInstance()
    if (!chart) return
    const zoom = (
      chart.getOption().dataZoom as DataZoomOptionEntry[] | undefined
    )?.[0]
    if (!zoom) return
    const last = barCountRef.current - 1
    const start =
      zoom.startValue != null
        ? Number(zoom.startValue)
        : Math.round(((zoom.start ?? 0) / 100) * last)
    const end =
      zoom.endValue != null
        ? Number(zoom.endValue)
        : Math.round(((zoom.end ?? 100) / 100) * last)
    windowRef.current = { start, end }
  }, [])

  const onEvents = {
    datazoom: syncWindow,
    updateAxisPointer: (event: AxisPointerEvent) => {
      const value = event.axesInfo?.[0]?.value
      anchorRef.current = value != null ? Number(value) : null
    },
  }

  const wrapperProps = {
    onMouseEnter: () => {
      hoverRef.current = true
    },
    onMouseLeave: () => {
      hoverRef.current = false
      anchorRef.current = null
    },
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!hoverRef.current) return
      if (
        !['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)
      ) {
        return
      }
      const chart = chartRef.current?.getEchartsInstance()
      if (!chart) return
      event.preventDefault()

      if (!windowRef.current) syncWindow()
      const win = windowRef.current
      if (!win) return
      const last = barCountRef.current - 1
      if (last < MIN_SPAN) return
      const span = win.end - win.start + 1
      const anchor = anchorRef.current ?? win.end

      let { start, end } = win
      if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        const factor = event.key === 'ArrowUp' ? ZOOM_IN_FACTOR : ZOOM_OUT_FACTOR
        const newSpan = Math.min(last + 1, Math.max(MIN_SPAN, span * factor))
        const leftRatio = span > 1 ? (anchor - win.start) / (span - 1) : 0.5
        start = anchor - leftRatio * (newSpan - 1)
        end = start + newSpan - 1
      } else {
        const step =
          Math.max(1, Math.round(span * 0.05)) *
          (event.key === 'ArrowLeft' ? -1 : 1)
        start = win.start + step
        end = win.end + step
      }
      if (start < 0) {
        end -= start
        start = 0
      }
      if (end > last) {
        start -= end - last
        end = last
      }
      start = Math.max(0, Math.round(start))
      end = Math.min(last, Math.round(end))

      chart.dispatchAction({
        type: 'dataZoom',
        startValue: start,
        endValue: end,
      })
      windowRef.current = { start, end }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [syncWindow])

  return { chartRef, wrapperProps, onEvents }
}
