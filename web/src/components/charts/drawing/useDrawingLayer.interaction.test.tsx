/**
 * useDrawingLayer 交互护栏测试（真实 echarts 实例）——图层拆分前置锁定现行为：
 * ① 拖拽交互：经 zrender handler 真实管线（命中测试 + Draggable drift）模拟
 *    mousedown→mousemove→mouseup；锚点拖拽形状跟随并落库 anchors，move 拖拽
 *    兄弟镜像 + dragMoved 阈值；
 * ② AI 图层渲染：徽标 -1/-2 常驻、命中线 -3 仅编辑态、非编辑态无交互属性；
 * ③ armed 门控：activeTool 置位 → 全部 dataZoom disabled + tooltip/axisPointer
 *    隐藏，退出还原，armed 态 teardown 还原。
 *
 * 注：echarts graphic text 在 SVG renderer 的 displayList 中不携带 option id
 * （以 tspan 形态存在），文字类断言走 SVG 文本内容。
 */
import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Mock } from 'vitest'
import * as echarts from 'echarts'

import type { AiDrawingItem, UserKlineDrawing } from './types'
import { DRAWING_ROOT_PREFIX } from './types'
import { useDrawingLayer } from './useDrawingLayer'

type Chart = ReturnType<typeof makeChart>

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

const noop = () => {}
/** 经 zrender 真实管线派发鼠标事件（含命中测试与 Draggable drift） */
const dispatch = (chart: Chart, type: 'mousedown' | 'mousemove' | 'mouseup', x: number, y: number) =>
  chart.getZr().handler.dispatch(type, {
    zrX: x,
    zrY: y,
    which: 1,
    preventDefault: noop,
    stopPropagation: noop,
    stopImmediatePropagation: noop,
  })

const DATES = ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04']

const trendline = (): UserKlineDrawing => ({
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
  style: { color: '#f0b429', lineStyle: 'solid', width: 2 },
})

const hline = (): UserKlineDrawing => ({
  id: '102',
  targetType: 'stock',
  targetCode: '000001',
  period: 'daily',
  drawingType: 'hline',
  anchors: [{ date: '', price: 5 }],
  direction: undefined,
  text: undefined,
  style: { color: '#f0b429', lineStyle: 'solid', width: 1 },
})

const aiTrend = (): AiDrawingItem => ({
  id: 'g1:压力位',
  label: '压力位',
  drawingType: 'trendline',
  anchors: [
    { date: '2026-09-01', price: 3 },
    { date: '2026-09-04', price: 8 },
  ],
  direction: undefined,
  reason: '两次受阻回落',
})

const elId = (kind: 'user' | 'ai', key: string, suffix: string) =>
  `${DRAWING_ROOT_PREFIX}${kind}-${key}${suffix}`

const findEl = (chart: Chart, id: string) =>
  chart.getZr().storage.getDisplayList().find((e) => e && String(e.id) === id) as
    | (Record<string, unknown> & { x?: number; y?: number; shape?: Record<string, number> })
    | undefined

const pxOf = (chart: Chart, dateIdx: number, price: number) => ({
  x: chart.convertToPixel({ xAxisIndex: 0 }, dateIdx) as number,
  y: chart.convertToPixel({ yAxisIndex: 0 }, price) as number,
})

function setup(
  chart: Chart,
  overrides: Partial<{
    drawings: UserKlineDrawing[]
    aiDrawings: AiDrawingItem[]
    activeTool: 'trendline' | null
    interactive: boolean
    selectedId: string | null
  }> = {},
) {
  const onUpdate = vi.fn()
  const hook = renderHook(
    (props: {
      drawings: UserKlineDrawing[]
      aiDrawings: AiDrawingItem[]
      activeTool: 'trendline' | null
      interactive: boolean
      selectedId: string | null
    }) =>
      useDrawingLayer({
        chart,
        dates: DATES,
        scope: { targetType: 'stock', targetCode: '000001', period: 'daily' },
        drawings: props.drawings,
        aiDrawings: props.aiDrawings,
        activeTool: props.activeTool,
        selectedId: props.selectedId,
        interactive: props.interactive,
        defaultStyle: { color: '#f0b429', lineStyle: 'solid', width: 2 },
        onCreate: () => {},
        onUpdate,
        onSelect: () => {},
        onDelete: () => {},
        onUpdateAiItem: () => {},
        onDeleteAiItem: () => {},
        onRequestDisarm: () => {},
        onRequestTextInput: () => {},
      }),
    {
      initialProps: {
        drawings: overrides.drawings ?? [],
        aiDrawings: overrides.aiDrawings ?? [],
        activeTool: overrides.activeTool ?? null,
        interactive: overrides.interactive ?? true,
        selectedId: overrides.selectedId ?? null,
      },
    },
  )
  return { onUpdate, hook }
}

const svgText = (chart: Chart) => chart.getDom().querySelector('svg')?.textContent ?? ''

describe('useDrawingLayer 拖拽交互', () => {
  it('锚点拖拽：形状跟随 drift 重下发，mouseup 落库换算后的数据锚点', () => {
    const chart = makeChart()
    const { onUpdate, hook } = setup(chart, { drawings: [trendline()], selectedId: '101' })
    const start = pxOf(chart, 0, 2)
    const line = findEl(chart, elId('user', '101', '-0'))!
    const x1Before = line.shape!.x1 as number
    const y1Before = line.shape!.y1 as number

    dispatch(chart, 'mousedown', start.x, start.y)
    // 小步移动：命中测试须始终落在被拖手柄上（真实指针轨迹）
    for (let i = 1; i <= 10; i++) dispatch(chart, 'mousemove', start.x + 3 * i, start.y - 2 * i)

    const moved = findEl(chart, elId('user', '101', '-0'))!
    expect(moved.shape!.x1).toBeCloseTo(x1Before + 30, 0)
    expect(moved.shape!.y1).toBeCloseTo(y1Before - 20, 0)

    dispatch(chart, 'mouseup', start.x + 30, start.y - 20)
    expect(onUpdate).toHaveBeenCalledTimes(1)
    const [id, patch] = (onUpdate as Mock).mock.calls[0]
    expect(id).toBe('101')
    expect(patch.anchors).toHaveLength(2)
    expect(patch.anchors[0].price).toBeGreaterThan(2) // y 上移 → 价格变高
    expect(patch.anchors[1].date).toBe('2026-09-03') // 未拖动锚点回换算不变
    hook.unmount()
    chart.dispose()
  })

  it('move 拖拽：兄弟元素经 storage 镜像位移，mouseup 落库整体平移锚点（hline 只带价格）', () => {
    const chart = makeChart()
    const { onUpdate, hook } = setup(chart, { drawings: [hline()], selectedId: null })
    const start = pxOf(chart, 2, 5)

    dispatch(chart, 'mousedown', start.x, start.y)
    for (let i = 1; i <= 5; i++) dispatch(chart, 'mousemove', start.x, start.y + 3 * i)

    const vis = findEl(chart, elId('user', '102', '-0'))!
    expect(vis.y).toBe(15) // 兄弟镜像（被抓命中线由 zrender 原生移动）

    dispatch(chart, 'mouseup', start.x, start.y + 15)
    expect(onUpdate).toHaveBeenCalledTimes(1)
    const [, patch] = (onUpdate as Mock).mock.calls[0]
    expect(patch.anchors[0].date).toBe('') // hline 契约：无 date
    expect(patch.anchors[0].price).toBeLessThan(5) // y 下移 → 价格变低
    hook.unmount()
    chart.dispose()
  })

  it('纯点击（无位移）不提交更新：dragMoved 阈值', () => {
    const chart = makeChart()
    const { onUpdate, hook } = setup(chart, { drawings: [hline()], selectedId: null })
    const start = pxOf(chart, 2, 5)
    dispatch(chart, 'mousedown', start.x, start.y)
    dispatch(chart, 'mouseup', start.x, start.y)
    expect(onUpdate).not.toHaveBeenCalled()
    hook.unmount()
    chart.dispose()
  })
})

describe('useDrawingLayer AI 图层渲染', () => {
  it('徽标 -1/-2 常驻；命中线 -3 仅编辑态；非编辑态元素无交互属性', () => {
    const chart = makeChart()
    const { hook } = setup(chart, { aiDrawings: [aiTrend()], interactive: false })

    const base = 'g1:压力位'
    expect(findEl(chart, elId('ai', base, '-0'))).toBeDefined()
    expect(findEl(chart, elId('ai', base, '-1'))).toBeDefined() // 徽标 rect
    expect(svgText(chart)).toContain('AI') // 徽标 text（displayList 无 id，走 SVG 文本）
    expect(findEl(chart, elId('ai', base, '-3'))).toBeUndefined() // 命中线仅编辑态
    const vis = findEl(chart, elId('ai', base, '-0'))!
    expect(vis.draggable).toBeFalsy()
    expect(vis.onclick).toBeUndefined()
    expect(vis.onmousedown).toBeUndefined()

    hook.rerender({
      drawings: [],
      aiDrawings: [aiTrend()],
      activeTool: null,
      interactive: true,
      selectedId: null,
    })
    expect(findEl(chart, elId('ai', base, '-3'))).toBeDefined()
    // 交互属性挂在 -3 命中线上（-0 可见线仅 hover 展示，两种模式都不参与拖拽）
    const hit = findEl(chart, elId('ai', base, '-3'))!
    expect(hit.draggable).toBe(true)
    expect(typeof hit.onmousedown).toBe('function')
    hook.unmount()
    chart.dispose()
  })
})

describe('useDrawingLayer armed 门控', () => {
  it('activeTool 置位禁用全部 dataZoom 并隐藏 tooltip/axisPointer，退出还原，armed 态 teardown 还原', () => {
    const chart = makeChart()
    const calls: string[] = []
    const orig = chart.setOption.bind(chart)
    chart.setOption = ((o: unknown) => {
      calls.push(JSON.stringify(o))
      return orig(o as never)
    }) as typeof chart.setOption

    const { hook } = setup(chart, { drawings: [trendline()] })
    calls.length = 0

    // armed：dataZoom 全部禁用 + 主图浮层隐藏（首次进入才保存原状态）
    hook.rerender({ drawings: [trendline()], aiDrawings: [], activeTool: 'trendline', interactive: true, selectedId: null })
    expect(calls).toContain('{"dataZoom":[{"disabled":true}]}')
    expect(calls).toContain('{"tooltip":{"show":false},"axisPointer":{"show":false}}')

    // 退出 armed：dataZoom 还原 + 浮层按保存的原状态还原
    calls.length = 0
    hook.rerender({ drawings: [trendline()], aiDrawings: [], activeTool: null, interactive: true, selectedId: null })
    expect(calls).toContain('{"dataZoom":[{"disabled":false}]}')
    expect(calls).toContain('{"tooltip":{"show":true},"axisPointer":{"show":true}}')

    // armed 态 teardown：卸载时还原 dataZoom 与浮层
    calls.length = 0
    hook.rerender({ drawings: [trendline()], aiDrawings: [], activeTool: 'trendline', interactive: true, selectedId: null })
    calls.length = 0
    hook.unmount()
    expect(calls.some((c) => c.includes('"disabled":false'))).toBe(true)
    expect(calls.some((c) => c.includes('"tooltip":{"show":true}'))).toBe(true)
    chart.dispose()
  })
})
