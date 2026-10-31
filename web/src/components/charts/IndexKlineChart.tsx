import ReactECharts from '@/components/charts/ReactECharts'
import type { ECharts } from 'echarts'
import { useEffect, useMemo, useState } from 'react'

import type { IndexKlineBar, KlineDrawingPeriod, MovingAverageConfig } from '@ai-invest/shared'
import { DrawingLayerHost } from '@/components/charts/drawing/DrawingLayerHost'
import { AiDrawingButton } from '@/components/charts/drawing/AiDrawingButton'
import { DrawingToolbar } from '@/components/charts/drawing/DrawingToolbar'
import {
  buildIndexKlineOption,
  initialVisibleWindow,
} from '@/components/charts/indexKlineOption'
import { useDataZoomYAxisRescale } from '@/components/charts/useDataZoomYAxisRescale'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useColorScheme } from '@/stores/settings'
import { fallHex, riseHex } from '@/utils/formatters'

interface IndexKlineChartProps {
  bars: IndexKlineBar[]
  maConfigs: MovingAverageConfig[]
  height?: number
  defaultVisibleBars?: number
  /** 异动日竖线标注（日期须命中横轴，未命中的自动忽略）。 */
  markers?: { date: string; label?: string }[]
  /** 画线归属（指数代码 + 周期）；不传或周期不支持（季/年线）则不启用画线图层。 */
  drawingTarget?: { code: string; period: KlineDrawingPeriod }
  /** 价格/收益率小数位（债券收益率传 3，其余默认 2）。 */
  valueDecimals?: number
  /** 详情页开启底部滑块缩放；概览卡片保持 inside-only。 */
  showSlider?: boolean
}

/**
 * 指数 K 线：option 由 indexKlineOption 构造，本组件只负责交互（键盘缩放、
 * 双击复位、缩放窗口联动、画线宿主）与 MA 常驻数值行。
 */
export function IndexKlineChart({
  bars,
  maConfigs,
  height = 360,
  defaultVisibleBars,
  markers,
  drawingTarget,
  valueDecimals = 2,
  showSlider = false,
}: IndexKlineChartProps) {
  useColorScheme()
  const { chartRef, wrapperProps, onEvents: navOnEvents } = useKlineKeyboardNav(bars.length)
  // 画线图层实例（onChartReady 捕获）；未传 drawingTarget 时不启用
  const [drawingChart, setDrawingChart] = useState<ECharts | null>(null)
  // MA 数值行 / 双击复位共用可见窗口尾下标；null = 序列尾
  const [visibleEndIdx, setVisibleEndIdx] = useState<number | null>(null)

  const up = riseHex()
  const down = fallHex()
  const dates = useMemo(() => bars.map((bar) => bar.date), [bars])
  const hasOhlc =
    bars.length > 0 &&
    bars.every((bar) => bar.open != null && bar.high != null && bar.low != null)

  const { handleDataZoom } = useDataZoomYAxisRescale(
    chartRef,
    { dates, bars },
    {
      rescale: hasOhlc,
      onWindowChange: (_startIdx, endIdx) =>
        setVisibleEndIdx((prev) => (prev === endIdx ? prev : endIdx)),
    },
  )

  useEffect(() => {
    setVisibleEndIdx(null)
  }, [bars])

  // option 必须 memo：内联 formatter 每次渲染都是新引用，echarts-for-react
  // 深比较失配会以 notMerge 重设 option，把用户已缩放/平移的窗口重置掉
  const { option, mas } = useMemo(
    () =>
      buildIndexKlineOption({
        bars,
        maConfigs,
        markers,
        defaultVisibleBars,
        valueDecimals,
        showSlider,
        height,
        up,
        down,
      }),
    [bars, maConfigs, markers, defaultVisibleBars, valueDecimals, showSlider, height, up, down],
  )

  /** 双击复位：回到本图自己的初始窗口（而非固定的 50% 百分比窗口）。 */
  const resetZoom = () => {
    const chart = chartRef.current?.getEchartsInstance()
    if (!chart) return
    chart.dispatchAction({
      type: 'dataZoom',
      ...(initialVisibleWindow(bars.length, defaultVisibleBars) ?? { start: 0, end: 100 }),
    })
  }

  const onEvents = {
    ...navOnEvents,
    dblclick: resetZoom,
    datazoom: () => {
      navOnEvents.datazoom()
      handleDataZoom()
    },
  }

  const latestIdx = Math.max(bars.length - 1, 0)
  const legendIdx = Math.min(Math.max(visibleEndIdx ?? latestIdx, 0), latestIdx)

  return (
    <div {...wrapperProps} className="relative">
      {drawingTarget && (
        <div className="absolute top-1.5 right-3 z-10 flex items-center gap-px rounded-md border border-white/10 bg-[#1a1d24]/90 p-px">
          <DrawingToolbar />
          <AiDrawingButton />
        </div>
      )}
      {mas.length > 0 && bars.length > 0 && (
        // 常驻数值行：锚定可见窗口尾 bar（缩放/平移后跟随），避开右侧价格轴与画线工具
        <div
          className={`absolute top-1.5 left-[66px] z-10 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[11px] pointer-events-none ${
            drawingTarget ? 'right-[150px]' : 'right-[72px]'
          }`}
        >
          {mas.map((ma) => {
            const value = ma.values[legendIdx]
            return (
              <span key={ma.period} style={{ color: ma.color }}>
                MA{ma.period}: {value == null ? '--' : value.toFixed(valueDecimals)}
              </span>
            )
          })}
        </div>
      )}
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: `${height}px`, width: '100%' }}
        onEvents={onEvents}
        notMerge
        onChartReady={setDrawingChart}
      />
      {drawingTarget && (
        <DrawingLayerHost
          chart={drawingChart}
          dates={dates}
          target={{ targetType: 'index', targetCode: drawingTarget.code }}
          period={drawingTarget.period}
        />
      )}
    </div>
  )
}
