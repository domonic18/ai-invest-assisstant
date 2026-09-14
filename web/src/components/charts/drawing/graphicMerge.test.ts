/**
 * graphic 增量更新回归测试（扁平元素架构）。
 *
 * 缺陷背景：旧实现用 group children 承载每条画线，echarts graphic 父组簿记有两处内伤——
 * ①「旧 id remove + 新 id replace」组合下 remove 先处理、新父组排到更新队列末尾，id-less
 * children 与孤儿条目按 index 错配，createEl 收到 undefined 父容器抛 `Cannot read properties
 * of undefined (reading 'add')`，画线保存成功但刷新前不显示；②replace 移除 group 在 traverse
 * 中边删边遍历，尾部子元素漏删、elMap 遗留悬挂键。
 * 修复：全部扁平化——可见形状/命中线/手柄/徽标都是带唯一 id 的顶层元素，merge 更新、逐元素
 * remove 删除，完全绕开父组簿记。
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

/** 与 useDrawingLayer.userShapeSpecs 同构（hline：可见线 -0 + 透明命中线 -1，顶层扁平元素） */
function hlineSpecs(base: string, y: number) {
  return [
    {
      id: `${base}-0`,
      position: [0, 0],
      type: 'line',
      shape: { x1: grid.x, y1: y, x2: grid.x + grid.width, y2: y },
      style: { stroke: '#f00', lineWidth: 1, opacity: 1, lineDash: undefined },
    },
    {
      id: `${base}-1`,
      position: [0, 0],
      type: 'line',
      shape: { x1: grid.x, y1: y, x2: grid.x + grid.width, y2: y },
      style: { stroke: '#000', lineWidth: 10, opacity: 0 },
      cursor: 'move',
      draggable: true,
    },
  ]
}

/** 与 useDrawingLayer.handleSpecs 同构 */
function handleSpecs(base: string, y: number) {
  return [
    {
      id: `${base}-h0`,
      position: [0, 0],
      type: 'circle',
      shape: { cx: 400, cy: y, r: 4.5 },
      style: { fill: '#16181f', stroke: '#f00', lineWidth: 1.5 },
      cursor: 'crosshair',
      draggable: true,
    },
  ]
}

/** 与 useDrawingLayer.draftSpecs 同构 */
function draftSpecs(base: string, y: number) {
  return [
    {
      id: `${base}-0`,
      position: [0, 0],
      type: 'circle',
      shape: { cx: 300, cy: y, r: 4 },
      style: { fill: '#f00', stroke: '#16181f', lineWidth: 1 },
    },
    {
      id: `${base}-1`,
      position: [0, 0],
      type: 'line',
      shape: { x1: 300, y1: y, x2: 420, y2: y + 30 },
      style: { stroke: '#f00', lineWidth: 1.5, opacity: 1, lineDash: [4, 4] },
    },
  ]
}

const removes = (ids: string[]) => ids.map((id: string) => ({ id, $action: 'remove' }))

function apply(chart: echarts.ECharts, graphic: unknown[]) {
  chart.setOption({ graphic } as never)
}

describe('graphic merge 更新队列（扁平元素）', () => {
  it('锁死历史缺陷：group + id-less children 在「replace 新 id + remove 旧 id」下抛错', () => {
    const chart = makeChart()
    const groupSpec = (id: string, y: number) => ({
      id,
      type: 'group',
      $action: 'replace',
      position: [0, 0],
      children: hlineSpecs(`${id}-c`, y).map((s) => {
        const c = { ...(s as Record<string, unknown>) }
        delete c.id
        return c
      }),
    })
    apply(chart, [groupSpec('legacy-temp', 150)])
    expect(() =>
      apply(chart, [groupSpec('legacy-uuid', 150), { id: 'legacy-temp', $action: 'remove' }]),
    ).toThrow(/reading 'add'/)
    chart.dispose()
  })

  it('扁平架构全旅程：temp 创建 → 换正式 id → 选中/取消 → 草稿 → 提交 → 删除，零抛错', () => {
    const chart = makeChart()
    apply(chart, hlineSpecs('u-temp-1', 150))
    apply(chart, [...hlineSpecs('u-a', 150), ...removes(['u-temp-1-0', 'u-temp-1-1'])])
    apply(chart, [...hlineSpecs('u-a', 150), ...handleSpecs('u-a', 150)])
    apply(chart, [...hlineSpecs('u-a', 150), ...removes(['u-a-h0'])])
    apply(chart, [...hlineSpecs('u-a', 150), ...draftSpecs('draft-1', 200)])
    apply(chart, [...hlineSpecs('u-a', 150), ...hlineSpecs('u-temp-2', 200), ...removes(['draft-1-0', 'draft-1-1'])])
    apply(chart, [...hlineSpecs('u-a', 150), ...hlineSpecs('u-b', 200), ...handleSpecs('u-b', 200)])
    apply(chart, [...hlineSpecs('u-a', 150), ...removes(['u-b-0', 'u-b-1', 'u-b-h0'])])
    chart.dispose()
  })

  it('remove 未渲染过的 id 抛错：层内 removed 队列只允许含曾渲染的 id（拖拽保活守卫的依据）', () => {
    const chart = makeChart()
    apply(chart, hlineSpecs('u-a', 150))
    expect(() => apply(chart, [...hlineSpecs('u-a', 150), ...removes(['u-ghost-0'])])).toThrow(
      /Cannot read properties of undefined/,
    )
    chart.dispose()
  })

  it('merge 重置 position：zrender 原生位移后重下发归位', () => {
    const chart = makeChart()
    apply(chart, hlineSpecs('u-a', 150))
    const zr = chart.getZr() as unknown as {
      storage: { getDisplayList: () => ({ id?: string; x?: number; y?: number } | undefined)[] }
    }
    const find = (id: string) => zr.storage.getDisplayList().find((e) => e?.id === id)
    const el = find('u-a-1')
    expect(el).toBeTruthy()
    el!.x = 30
    el!.y = 12
    apply(chart, hlineSpecs('u-a', 150))
    const after = find('u-a-1')
    expect(after?.x).toBe(0)
    expect(after?.y).toBe(0)
    chart.dispose()
  })
})
