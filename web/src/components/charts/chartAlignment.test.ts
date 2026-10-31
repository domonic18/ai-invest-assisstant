/**
 * 多 grid 横向对齐回归：ECharts 6 默认 outerBoundsMode='auto' 会按各 grid 自身
 * 坐标轴标签宽度重算绘图区，主图与副图逐根错位（指数/个股均曾中招）。
 * option 断言锁定契约，SSR 渲染断言锁定最终绘图区矩形。
 */

import { describe, expect, it } from 'vitest'

import type { EChartsOption } from 'echarts'
import type { ECharts } from 'echarts'
import { SVGRenderer } from 'echarts/renderers'

import type { IndexKlineBar, MovingAverageConfig, StockKlineBar } from '@ai-invest/shared'
import { echarts } from '@/components/charts/echarts'
import {
  buildIndexKlineOption,
  initialVisibleWindow,
} from '@/components/charts/indexKlineOption'
import { computePriceAxisRange } from '@/components/charts/chartLayout'

import { prepareKlineData } from './stockChartView/klineData'
import { buildKlineOption } from './stockChartView/klineOption'

echarts.use([SVGRenderer])

const MA_CONFIGS: MovingAverageConfig[] = [{ period: 5, color: '#f0f1f5', enabled: true }]

const indexBar = (i: number): IndexKlineBar => ({
  date: `2026-01-${String(i + 1).padStart(2, '0')}`,
  open: 3000 + i,
  high: 3010 + i,
  low: 2990 + i,
  close: 3005 + i,
  volume: 1e8 + i * 1e6,
  amount: 4e11,
})

const closeOnlyBar = (i: number): IndexKlineBar => ({
  date: `2026-01-${String(i + 1).padStart(2, '0')}`,
  open: null,
  high: null,
  low: null,
  close: 2.1 + i * 0.001,
  volume: 0,
  amount: null,
})

const stockBar = (i: number): StockKlineBar => ({
  date: `2026-01-${String(i + 1).padStart(2, '0')}`,
  open: 10 + i,
  high: 12 + i,
  low: 9 + i,
  close: 11 + i,
  volume: 1_000_000 + i * 1000,
  amount: 1e8,
  changePct: null,
  amplitude: null,
  turnoverRate: null,
})

interface GridRect {
  x: number
  width: number
}

function renderRects(option: EChartsOption): GridRect[] {
  const chart: ECharts = echarts.init(null, null, {
    renderer: 'svg',
    ssr: true,
    width: 900,
    height: 460,
  })
  chart.setOption(option)
  const model = (
    chart as unknown as {
      getModel: () => {
        getComponent: (type: string, index: number) => {
          coordinateSystem: { getRect: () => { x: number; width: number } }
        } | undefined
      }
    }
  ).getModel()
  const rects: GridRect[] = []
  for (let i = 0; ; i += 1) {
    const grid = model.getComponent('grid', i)
    if (!grid) break
    const rect = grid.coordinateSystem.getRect()
    rects.push({ x: rect.x, width: rect.width })
  }
  chart.dispose()
  return rects
}

function gridOptions(option: EChartsOption) {
  return (option.grid ?? []) as Array<{
    left?: number
    right?: number
    outerBoundsMode?: string
  }>
}

describe('多 grid 对齐契约', () => {
  it('指数 K 线（蜡烛 + 量能）两个 grid 共享左右边界且关闭 outerBounds 自适应', () => {
    const bars = Array.from({ length: 80 }, (_, i) => indexBar(i))
    const { option } = buildIndexKlineOption({
      bars,
      maConfigs: MA_CONFIGS,
      defaultVisibleBars: 30,
      height: 400,
      up: '#e5484d',
      down: '#2ea043',
    })
    // 初始纵轴按可见窗口（后 30 根）定标，而非全序列
    const { yMin, yMax } = computePriceAxisRange(bars, 50, 79)
    expect((option.yAxis as Array<{ min?: number; max?: number }>)[0]).toMatchObject({
      min: yMin,
      max: yMax,
    })
    const grids = gridOptions(option)
    expect(grids).toHaveLength(2)
    for (const grid of grids) {
      expect(grid.left).toBe(60)
      expect(grid.right).toBe(64)
      expect(grid.outerBoundsMode).toBe('none')
    }
    const rects = renderRects(option)
    expect(rects).toHaveLength(2)
    expect(rects[1]).toEqual(rects[0])
  })

  it('个股 K 线（VOL + MACD）主图与副图绘图区完全一致', () => {
    const data = prepareKlineData(
      { bars: Array.from({ length: 80 }, (_, i) => stockBar(i)) },
      MA_CONFIGS,
    )
    const option = buildKlineOption(
      data,
      { volume: true, ma: true, macd: true, kdj: false },
      460,
    )
    const grids = gridOptions(option)
    expect(grids).toHaveLength(3)
    for (const grid of grids) {
      expect(grid.outerBoundsMode).toBe('none')
    }
    const rects = renderRects(option)
    expect(rects).toHaveLength(3)
    expect(rects[1]).toEqual(rects[0])
    expect(rects[2]).toEqual(rects[0])
  })

  it('个股 K 线同时开 VOL/MACD/KDJ 仍需产出四段窗格', () => {
    const data = prepareKlineData(
      { bars: Array.from({ length: 80 }, (_, i) => stockBar(i)) },
      [],
    )
    const option = buildKlineOption(
      data,
      { volume: true, ma: false, macd: true, kdj: true },
      460,
    )
    expect(gridOptions(option)).toHaveLength(4)
    const rects = renderRects(option)
    expect(rects).toHaveLength(4)
    expect(rects[3]).toEqual(rects[0])
  })
})

describe('指数收盘线模式', () => {
  function closeLineOption(valueDecimals?: number) {
    return buildIndexKlineOption({
      bars: Array.from({ length: 40 }, (_, i) => closeOnlyBar(i)),
      maConfigs: MA_CONFIGS,
      valueDecimals,
      height: 340,
      up: '#e5484d',
      down: '#2ea043',
    }).option
  }

  it('最新价胶囊与蜡烛模式一致，不再是纯异动线', () => {
    const option = closeLineOption()
    const line = (option.series as Array<{ name: string; markLine?: { data: unknown[] } }>).find(
      (s) => s.name === '收盘',
    )
    expect(line?.markLine?.data?.[0]).toMatchObject({ yAxis: closeOnlyBar(39).close })
  })

  it('收益率小数位透传到纵轴刻度', () => {
    const option = closeLineOption(3)
    const axis = (option.yAxis as Array<{ axisLabel: { formatter: (v: number) => string } }>)[0]
    expect(axis.axisLabel.formatter(2.1504)).toBe('2.150')
  })
})

describe('initialVisibleWindow', () => {
  it('不足窗口或无配置时返回 null（全量显示）', () => {
    expect(initialVisibleWindow(80, undefined)).toBeNull()
    expect(initialVisibleWindow(80, 120)).toBeNull()
  })

  it('按尾部 N 根生成 startValue/endValue', () => {
    expect(initialVisibleWindow(80, 30)).toEqual({ startValue: 50, endValue: 79 })
  })
})
