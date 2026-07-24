import { describe, expect, it } from 'vitest'

import {
  edgeStyleByCriticality,
  marginToOpacity,
  strengthToLineWidth,
} from './chainGraphStyle'

describe('marginToOpacity', () => {
  it('null 返回灰显透明度', () => {
    expect(marginToOpacity(null)).toBe(0.08)
  })

  it('0% 映射到下界 0.12', () => {
    expect(marginToOpacity(0)).toBeCloseTo(0.12)
  })

  it('60% 映射到上界 0.45', () => {
    expect(marginToOpacity(60)).toBeCloseTo(0.45)
  })

  it('30% 线性映射到中间值', () => {
    expect(marginToOpacity(30)).toBeCloseTo(0.285)
  })

  it('超出 60% 截断到上界', () => {
    expect(marginToOpacity(120)).toBeCloseTo(0.45)
  })

  it('负值截断到下界', () => {
    expect(marginToOpacity(-5)).toBeCloseTo(0.12)
  })
})

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
    expect(style.stroke).toBe('#5e6ad2')
    expect(style.lineDash).toBeUndefined()
  })

  it('medium 为灰蓝实线', () => {
    const style = edgeStyleByCriticality('medium')
    expect(style.stroke).toBe('#7c8bb5')
    expect(style.lineDash).toBeUndefined()
  })

  it('low 为灰色虚线', () => {
    const style = edgeStyleByCriticality('low')
    expect(style.stroke).toBe('#6b7280')
    expect(style.lineDash).toEqual([6, 4])
  })

  it('null 为灰色虚线', () => {
    const style = edgeStyleByCriticality(null)
    expect(style.stroke).toBe('#6b7280')
    expect(style.lineDash).toEqual([6, 4])
  })
})
