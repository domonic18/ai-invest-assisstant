import { describe, expect, it } from 'vitest'

import type { ChainNode } from '@ai-invest/shared'

import {
  buildSignalBadges,
  edgeStyleByCriticality,
  strengthToLineWidth,
  techBarrierColor,
  techBarrierLabel,
  truncateLabel,
} from './chainGraphStyle'

function makeNode(overrides: Partial<ChainNode>): ChainNode {
  return {
    name: '光刻胶',
    type: 'upstream',
    description: '',
    companies: [],
    avgGrossMargin: null,
    revenueGrowth: null,
    rdRatio: null,
    bargainingPower: null,
    localizationRate: null,
    techBarrier: null,
    bottleneckIndicators: [],
    recentBreakthroughs: [],
    ...overrides,
  }
}

describe('strengthToLineWidth', () => {
  it('null/undefined 返回最细 1px', () => {
    expect(strengthToLineWidth(null)).toBe(1)
    expect(strengthToLineWidth(undefined)).toBe(1)
  })

  it('0 映射到 1px，100 映射到 5px', () => {
    expect(strengthToLineWidth(0)).toBe(1)
    expect(strengthToLineWidth(100)).toBe(5)
  })

  it('50 映射到中间 3px', () => {
    expect(strengthToLineWidth(50)).toBe(3)
  })

  it('超界截断', () => {
    expect(strengthToLineWidth(-10)).toBe(1)
    expect(strengthToLineWidth(999)).toBe(5)
  })
})

describe('edgeStyleByCriticality', () => {
  it('high 为主题色实线', () => {
    const style = edgeStyleByCriticality('high')
    expect(style.stroke).toBe('#6366f1')
    expect(style.lineDash).toBeUndefined()
  })

  it('medium 为灰实线', () => {
    const style = edgeStyleByCriticality('medium')
    expect(style.stroke).toBe('#9ca3af')
    expect(style.lineDash).toBeUndefined()
  })

  it('low/null 为暗色半透明虚线', () => {
    for (const criticality of ['low', null] as const) {
      const style = edgeStyleByCriticality(criticality)
      expect(style.stroke).toBe('rgba(255,255,255,0.2)')
      expect(style.lineDash).toEqual([6, 4])
    }
  })
})

describe('techBarrierLabel / techBarrierColor', () => {
  it('high/medium/low 映射中文标签', () => {
    expect(techBarrierLabel('high')).toBe('高')
    expect(techBarrierLabel('medium')).toBe('中')
    expect(techBarrierLabel('low')).toBe('低')
  })

  it('null 或未知值返回 —', () => {
    expect(techBarrierLabel(null)).toBe('—')
    expect(techBarrierLabel('extreme')).toBe('—')
  })

  it('high 红色、medium 琥珀、其他灰色', () => {
    expect(techBarrierColor('high')).toBe('#ef4444')
    expect(techBarrierColor('medium')).toBe('#d29922')
    expect(techBarrierColor('low')).toBe('#6b7280')
    expect(techBarrierColor(null)).toBe('#6b7280')
  })
})

describe('buildSignalBadges', () => {
  it('突破优先，瓶颈补充，默认最多 2 个', () => {
    const node = makeNode({
      recentBreakthroughs: ['ArF验证中', '大基金注资', '扩产'],
      bottleneckIndicators: ['依赖进口'],
    })
    const badges = buildSignalBadges(node)
    expect(badges).toHaveLength(2)
    expect(badges[0]).toMatchObject({ icon: '⚡', text: 'ArF验证中' })
    expect(badges[1]).toMatchObject({ icon: '⚡', text: '大基金注资' })
  })

  it('突破不足时由瓶颈补齐', () => {
    const node = makeNode({
      recentBreakthroughs: ['验证通过'],
      bottleneckIndicators: ['国产化率低', '设备受限'],
    })
    const badges = buildSignalBadges(node)
    expect(badges).toHaveLength(2)
    expect(badges[0].icon).toBe('⚡')
    expect(badges[1]).toMatchObject({ icon: '⚠', text: '国产化率低' })
  })

  it('无信号时返回空数组', () => {
    expect(buildSignalBadges(makeNode({}))).toEqual([])
  })
})

describe('truncateLabel', () => {
  it('超长截断并加省略号', () => {
    expect(truncateLabel('一二三四五六', 4)).toBe('一二三…')
  })

  it('未超长原样返回', () => {
    expect(truncateLabel('短', 4)).toBe('短')
  })
})
