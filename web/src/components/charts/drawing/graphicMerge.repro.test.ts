/**
 * 临时复现测试：ECharts graphic children + $action:'replace' 混用序列，
 * 定位「Cannot read properties of undefined (reading 'add')」。用完即删或转回归测试。
 */
import { describe, expect, it } from 'vitest'
import * as echarts from 'echarts'

function makeChart() {
  const div = document.createElement('div')
  document.body.appendChild(div)
  const chart = echarts.init(div, null, { renderer: 'svg', width: 800, height: 400 })
  chart.setOption({
    animation: false,
    xAxis: { type: 'category', data: ['a', 'b', 'c', 'd', 'e'] },
    yAxis: {},
    series: [{ type: 'candlestick', data: [[1, 2, 0.5, 2.5], [2, 3, 1, 3.5], [3, 2, 1.5, 3.2], [2, 2.5, 1.8, 2.8], [2.5, 3.5, 2.2, 4]] }],
    dataZoom: [{ type: 'inside' }],
  })
  return chart
}

const grid = { x: 60, y: 20, width: 700, height: 350 }

function hlineSpec(id: string, y: number) {
  return {
    id,
    type: 'group',
    $action: 'replace',
    position: [0, 0],
    children: [
      { type: 'line', shape: { x1: grid.x, y1: y, x2: grid.x + grid.width, y2: y }, style: { stroke: '#f00', lineWidth: 1, opacity: 1, lineDash: undefined } },
      { type: 'line', shape: { x1: grid.x, y1: y, x2: grid.x + grid.width, y2: y }, style: { stroke: '#000', lineWidth: 10, opacity: 0 }, cursor: 'move', draggable: true },
    ],
  }
}

function handlesSpec(id: string, y: number) {
  return {
    id,
    type: 'group',
    $action: 'replace',
    children: [
      { type: 'circle', shape: { cx: 400, cy: y, r: 4.5 }, position: [0, 0], style: { fill: '#16181f', stroke: '#f00', lineWidth: 1.5 }, cursor: 'crosshair', draggable: true },
    ],
  }
}

function draftSpec(y: number) {
  return {
    id: 'kline-drawing-rootdraft',
    type: 'group',
    $action: 'replace',
    children: [
      { type: 'circle', shape: { cx: 300, cy: y, r: 4 }, style: { fill: '#f00', stroke: '#16181f', lineWidth: 1 } },
      { type: 'line', shape: { x1: 300, y1: y, x2: 420, y2: y + 30 }, style: { stroke: '#f00', lineWidth: 1.5, opacity: 1, lineDash: [4, 4] } },
    ],
  }
}

function apply(chart: echarts.ECharts, graphic: unknown[]) {
  // 与 useDrawingLayer 出口一致：数组直接下发
  chart.setOption({ graphic } as never)
}

describe('graphic merge bisect', () => {
  it('reproduces user sequence', () => {
    const chart = makeChart()
    // 1. 乐观追加（temp id）
    expect(() => apply(chart, [hlineSpec('kline-drawing-rootuser-temp-1', 150)])).not.toThrow()
    // 2. temp → server id（replace + remove 旧 id）
    expect(() =>
      apply(chart, [hlineSpec('kline-drawing-rootuser-uuid-a', 150), { id: 'kline-drawing-rootuser-temp-1', $action: 'remove' }]),
    ).not.toThrow()
    // 3. 选中 → handles 出现
    expect(() => apply(chart, [hlineSpec('kline-drawing-rootuser-uuid-a', 150), handlesSpec('kline-drawing-rootuser-uuid-a-handles', 150)])).not.toThrow()
    // 4. 取消选中 → handles 移除
    expect(() => apply(chart, [hlineSpec('kline-drawing-rootuser-uuid-a', 150), { id: 'kline-drawing-rootuser-uuid-a-handles', $action: 'remove' }])).not.toThrow()
    // 5. 草稿出现（第二笔画线）
    expect(() => apply(chart, [hlineSpec('kline-drawing-rootuser-uuid-a', 150), draftSpec(200)])).not.toThrow()
    // 6. 草稿提交 → draft 移除 + 第二条线追加
    expect(() =>
      apply(chart, [
        hlineSpec('kline-drawing-rootuser-uuid-a', 150),
        hlineSpec('kline-drawing-rootuser-temp-2', 200),
        { id: 'kline-drawing-rootdraft', $action: 'remove' },
      ]),
    ).not.toThrow()
    chart.dispose()
    div_remove()
    function div_remove() {
      /* noop placeholder */
    }
  })

  it('draft first (before any drawing)', () => {
    const chart = makeChart()
    expect(() => apply(chart, [draftSpec(120)])).not.toThrow()
    expect(() => apply(chart, [])).not.toThrow()
    chart.dispose()
  })

  it('empty children group', () => {
    const chart = makeChart()
    expect(() =>
      apply(chart, [{ id: 'g-empty', type: 'group', $action: 'replace', position: [0, 0], children: [] }]),
    ).not.toThrow()
    // 空组后重新下发带 children 的同名组
    expect(() => apply(chart, [hlineSpec('g-empty', 180)])).not.toThrow()
    chart.dispose()
  })
})
