import { describe, expect, it } from 'vitest'

import {
  DRAG_COMMIT_THRESHOLD,
  isTwoAnchorTool,
  moveDraft,
  pressSecond,
  releaseDraft,
  startDraft,
} from './draftMachine'

const pt = (x: number, y: number) => ({ x, y })

describe('isTwoAnchorTool', () => {
  it('trendline/ray/box 为双锚点，hline/text 不是', () => {
    expect(isTwoAnchorTool('trendline')).toBe(true)
    expect(isTwoAnchorTool('ray')).toBe(true)
    expect(isTwoAnchorTool('box')).toBe(true)
    expect(isTwoAnchorTool('hline')).toBe(false)
    expect(isTwoAnchorTool('text')).toBe(false)
  })
})

describe('startDraft', () => {
  it('双锚点工具进入 pressing 草稿', () => {
    const d = startDraft('ray', pt(10, 20))
    expect(d).toEqual({ tool: 'ray', phase: 'pressing', startPx: pt(10, 20), cursorPx: pt(10, 20) })
  })

  it('单锚点工具不开草稿（集成层 click 直接提交）', () => {
    expect(startDraft('hline', pt(0, 0))).toBeNull()
    expect(startDraft('text', pt(0, 0))).toBeNull()
  })
})

describe('moveDraft', () => {
  it('仅更新预览终点，不提交', () => {
    const d = startDraft('trendline', pt(0, 0))!
    const t = moveDraft(d, pt(100, 50))
    expect(t.commit).toBeNull()
    expect(t.session?.cursorPx).toEqual(pt(100, 50))
    expect(t.session?.phase).toBe('pressing')
    expect(t.session?.startPx).toEqual(pt(0, 0))
  })
})

describe('releaseDraft', () => {
  it('位移达阈值：拖拽式直接成线并终结草稿', () => {
    const d = startDraft('box', pt(0, 0))!
    const t = releaseDraft(d, pt(200, 80))
    expect(t.commit).toEqual([pt(0, 0), pt(200, 80)])
    expect(t.session).toBeNull()
  })

  it('纯点击（位移小于阈值）：转入 awaitSecond 等第二下', () => {
    const d = startDraft('trendline', pt(10, 10))!
    const t = releaseDraft(d, pt(12, 11))
    expect(t.commit).toBeNull()
    expect(t.session?.phase).toBe('awaitSecond')
    expect(t.session?.startPx).toEqual(pt(10, 10))
  })

  it('阈值判断含边界（恰为 6px 成线）', () => {
    const d = startDraft('ray', pt(0, 0))!
    expect(releaseDraft(d, pt(DRAG_COMMIT_THRESHOLD, 0)).commit).not.toBeNull()
    const d2 = startDraft('ray', pt(0, 0))!
    const below = releaseDraft(d2, pt(DRAG_COMMIT_THRESHOLD - 1, 0))
    expect(below.commit).toBeNull()
    expect(below.session?.phase).toBe('awaitSecond')
  })

  it('位移按欧氏距离度量（3-4-5 直角边仍小于阈值）', () => {
    const d = startDraft('trendline', pt(0, 0))!
    expect(releaseDraft(d, pt(3, 4)).commit).toBeNull()
  })
})

describe('pressSecond', () => {
  it('等待第二下时落点成线：start→pt，草稿终结', () => {
    const d = startDraft('trendline', pt(5, 5))!
    const promoted = releaseDraft(d, pt(6, 6)).session!
    const t = pressSecond(promoted, pt(300, 120))
    expect(t.commit).toEqual([pt(5, 5), pt(300, 120)])
    expect(t.session).toBeNull()
  })
})
