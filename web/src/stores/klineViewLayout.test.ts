import { describe, expect, it } from 'vitest'

import {
  resolveZoomWindow,
  useKlineViewLayoutStore,
} from './klineViewLayout'

describe('resolveZoomWindow', () => {
  it('按新数据长度恢复 span 并锚定右端偏移', () => {
    expect(resolveZoomWindow({ span: 60, endOffset: 0 }, 250)).toEqual({
      start: 190,
      end: 249,
    })
    expect(resolveZoomWindow({ span: 60, endOffset: 10 }, 250)).toEqual({
      start: 180,
      end: 239,
    })
  })

  it('span 超过新数据总长时收缩到全长', () => {
    expect(resolveZoomWindow({ span: 300, endOffset: 0 }, 250)).toEqual({
      start: 0,
      end: 249,
    })
  })

  it('回看偏移越过左缘时贴左缘并保持 span', () => {
    expect(resolveZoomWindow({ span: 50, endOffset: 240 }, 250)).toEqual({
      start: 0,
      end: 49,
    })
  })

  it('退化输入安全', () => {
    expect(resolveZoomWindow({ span: 5, endOffset: 0 }, 1)).toEqual({
      start: 0,
      end: 0,
    })
  })
})

describe('klineViewLayout store', () => {
  it('dual/periods/windows 按视图槽位独立读写', () => {
    useKlineViewLayoutStore.setState({ dual: false, periods: {}, windows: {} })
    const s = useKlineViewLayoutStore.getState()
    s.setDual(true)
    s.setPeriod('daily', 'monthly')
    s.setPeriod('weekly', 'weekly')
    s.setWindow('daily', { span: 60, endOffset: 3 })

    const state = useKlineViewLayoutStore.getState()
    expect(state.dual).toBe(true)
    expect(state.periods).toEqual({ daily: 'monthly', weekly: 'weekly' })
    expect(state.windows.daily).toEqual({ span: 60, endOffset: 3 })
    expect(state.windows.weekly).toBeUndefined()
  })
})
