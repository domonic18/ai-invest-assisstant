/**
 * useDrawingLayer 渲染链路回归测试（真实 echarts 实例）。
 *
 * 覆盖三类用户可感缺陷的渲染侧回归：
 * - 样式变更（虚线/实线切换）必须经 graphic merge 落到已存在元素；
 * - hline（date 为空的锚点）像素定位不应落到图表右缘；
 * - 锚点更新（拖拽落库后）文字元素跟随新坐标。
 */
import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import * as echarts from 'echarts'

import type { UserKlineDrawing } from './types'
import { DRAWING_ROOT_PREFIX } from './types'
import { useDrawingLayer } from './useDrawingLayer'

const elId = (drawingId: string, suffix: string) => `${DRAWING_ROOT_PREFIX}user-${drawingId}${suffix}`

function makeChart() {
  const div = document.createElement('div')
  document.body.appendChild(div)
  const chart = echarts.init(div, null, { renderer: 'svg', width: 800, height: 400 })
  chart.setOption({
    animation: false,
    grid: { left: 60, top: 20, width: 700, height: 350 },
    xAxis: { type: 'category', data: ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04'] },
    yAxis: { min: 0, max: 10 },
    series: [{ type: 'candlestick', data: [[1, 2, 0.5, 2.5], [2, 3, 1, 3.5], [3, 2, 1.5, 3.2], [2, 2.5, 1.8, 2.8]] }],
    dataZoom: [{ type: 'inside' }],
  })
  return chart
}

const DATES = ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04']

const trendline = (lineStyle: 'solid' | 'dashed'): UserKlineDrawing => ({
  id: '101',
  targetType: 'stock',
  targetCode: '000001',
  period: 'daily',
  drawingType: 'trendline',
  anchors: [
    { date: '2026-09-01', price: 2 },
    { date: '2026-09-03', price: 6 },
  ],
  direction: undefined,
  text: undefined,
  style: { color: '#f0b429', lineStyle, width: 2 },
})

const hline: UserKlineDrawing = {
  id: '102',
  targetType: 'stock',
  targetCode: '000001',
  period: 'daily',
  drawingType: 'hline',
  anchors: [{ date: '', price: 5 }],
  direction: undefined,
  text: undefined,
  style: { color: '#f0b429', lineStyle: 'solid', width: 1 },
}

const textDrawing = (date: string): UserKlineDrawing => ({
  id: '103',
  targetType: 'stock',
  targetCode: '000001',
  period: 'daily',
  drawingType: 'text',
  anchors: [{ date, price: 4 }],
  direction: undefined,
  text: '标注',
  style: { color: '#f0b429', lineStyle: 'solid', width: 2 },
})

function setup(chart: ReturnType<typeof makeChart>, drawings: UserKlineDrawing[], selectedId: string | null) {
  const noop = () => {}
  return renderHook(
    (props: { drawings: UserKlineDrawing[]; selectedId: string | null }) =>
      useDrawingLayer({
        chart,
        dates: DATES,
        scope: { targetType: 'stock', targetCode: '000001', period: 'daily' },
        drawings: props.drawings,
        aiDrawings: [],
        activeTool: null,
        selectedId: props.selectedId,
        interactive: true,
        defaultStyle: { color: '#f0b429', lineStyle: 'solid', width: 2 },
        onCreate: noop,
        onUpdate: noop,
        onSelect: noop,
        onDelete: noop,
        onUpdateAiItem: noop,
        onDeleteAiItem: noop,
        onRequestDisarm: noop,
        onRequestTextInput: noop,
      }),
    { initialProps: { drawings, selectedId } },
  )
}

const findEl = (chart: ReturnType<typeof makeChart>, id: string) =>
  chart.getZr().storage.getDisplayList().find((e) => e && String(e.id) === id)

describe('useDrawingLayer 渲染链路', () => {
  it('样式切换 solid→dashed 经 graphic merge 落到既有元素', () => {
    const chart = makeChart()
    const hook = setup(chart, [trendline('solid')], '101')
    expect(findEl(chart, elId('101', '-0'))?.style.lineDash).toBeUndefined()

    hook.rerender({ drawings: [trendline('dashed')], selectedId: '101' })
    expect(findEl(chart, elId('101', '-0'))?.style.lineDash).toEqual([7, 5])

    hook.rerender({ drawings: [trendline('solid')], selectedId: '101' })
    expect(findEl(chart, elId('101', '-0'))?.style.lineDash).toBeUndefined()
    hook.unmount()
  })

  it('hline 无 date 锚点的像素定位落在绘图区水平中心（不贴右缘）', () => {
    const chart = makeChart()
    const hook = setup(chart, [hline], '102')
    const { getSelectedPixelPos } = hook.result.current
    const pos = getSelectedPixelPos()
    expect(pos).not.toBeNull()
    // grid: x=60, width=700 → 水平中心 410；此前空 date 会吸附到最后一根 bar（右缘）
    expect(pos!.x).toBeCloseTo(410, 5)
    expect(pos!.y).toBeGreaterThan(20)
    expect(pos!.y).toBeLessThan(370)
    hook.unmount()
  })

  it('文字标注渲染为可见 SVG 文本且锚点更新不丢', () => {
    const chart = makeChart()
    const hook = setup(chart, [textDrawing('2026-09-01')], '103')
    // echarts graphic text 在 displayList 中以 tspan 形态存在（不携带 option id），
    // 用 SVG 文本内容断言可见性
    const svgText = () => chart.getDom().querySelector('svg')?.textContent ?? ''
    expect(svgText()).toContain('标注')

    hook.rerender({ drawings: [textDrawing('2026-09-04')], selectedId: '103' })
    expect(svgText()).toContain('标注')
    expect((svgText().match(/标注/g) ?? []).length).toBe(1)
    hook.unmount()
  })

  it('dataZoom 平移/缩放后画线跟随坐标系重定位', () => {
    const chart = makeChart()
    const hook = setup(chart, [trendline('solid')], '101')
    const before = findEl(chart, elId('101', '-0'))
    expect(before).toBeDefined()
    const shapeOf = (el: unknown) => (el as { shape: { x1: number } }).shape
    const xBefore = shapeOf(before).x1

    // 可视窗口缩到后 40%：首锚点（idx0）被推出绘图区左侧，画线必须重定位/裁剪
    chart.dispatchAction({ type: 'dataZoom', start: 60, end: 100 })
    const after = findEl(chart, elId('101', '-0'))
    const xAfter = shapeOf(after).x1
    expect(xAfter).toBeLessThan(xBefore)
    hook.unmount()
  })
})
