import { describe, expect, it } from 'vitest'

import { deriveChipVisual } from './chipState'

import { makeOverviewItem } from '../testFixtures'

describe('deriveChipVisual', () => {
  it('working → run：满载呼吸 + 四灯跑马 + 散热气流', () => {
    const v = deriveChipVisual(makeOverviewItem({ runtimeState: 'working' }))
    expect(v.mode).toBe('run')
    expect(v.dieBeat).toBe('ahc-corebeat')
    expect(v.led).toBe('chase')
    expect(v.heat).toBe(true)
    expect(v.codeText).toContain('RUN')
  })

  it('produced_today → 单灯常亮 + 慢呼吸 + 产出计数', () => {
    const v = deriveChipVisual(
      makeOverviewItem({ runtimeState: 'produced_today', planCount: 3, selectionCount: 9 }),
    )
    expect(v.mode).toBe('produced')
    expect(v.led).toBe('solid')
    expect(v.heat).toBe(false)
    expect(v.codeText).toContain('PRODUCED ×12')
  })

  it('paused → die 不上电 + 琥珀 LED 覆盖', () => {
    const v = deriveChipVisual(makeOverviewItem({ runtimeState: 'paused' }))
    expect(v.mode).toBe('paused')
    expect(v.dieBeat).toBeNull()
    expect(v.ledColorOverride).toBe('#f59e0b')
  })

  it('off → 空插槽（SOCKET EMPTY，LED 全灭）', () => {
    const v = deriveChipVisual(makeOverviewItem({ runtimeState: 'off' }))
    expect(v.mode).toBe('off')
    expect(v.codeText).toBe('SOCKET EMPTY · NO POWER')
    expect(v.led).toBe('none')
  })

  it('caption 优先后端 stateLabel（不虚报）', () => {
    const v = deriveChipVisual(
      makeOverviewItem({ runtimeState: 'working', stateLabel: '盯盘执行中 · 600000' }),
    )
    expect(v.caption).toBe('盯盘执行中 · 600000')
  })

  it('无 stateLabel 时回退五态默认文案', () => {
    expect(deriveChipVisual(makeOverviewItem({ runtimeState: 'idle' })).caption).toContain('待机')
  })
})
