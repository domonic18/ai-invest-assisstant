/**
 * 画线草稿状态机（纯函数，零 ECharts 依赖）：
 * 双锚点工具（趋势线/射线/箱体）支持「点击两下」与「按住拖拽释放」两种成线方式；
 * 单锚点工具（水平线/文字）由集成层在 click 直接提交，不经过本状态机。
 */

import type { KlineDrawingType, Point } from './types'

/** 拖拽释放成线的最小位移（px）：低于阈值视为纯点击，转入等待第二下 */
export const DRAG_COMMIT_THRESHOLD = 6

export const TWO_ANCHOR_TOOLS: ReadonlySet<string> = new Set(['trendline', 'ray', 'box'])

export function isTwoAnchorTool(tool: KlineDrawingType): boolean {
  return TWO_ANCHOR_TOOLS.has(tool)
}

/** 草稿阶段：pressing = 首锚点按住未释放；awaitSecond = 首锚点已定，等待第二下 */
export type DraftPhase = 'pressing' | 'awaitSecond'

export interface DraftSession {
  tool: KlineDrawingType
  phase: DraftPhase
  /** 首锚点像素 */
  startPx: Point
  /** 跟随光标的实时第二点（预览用） */
  cursorPx: Point
}

export interface DraftTransition {
  /** 下一草稿态（null = 草稿终结：提交或取消） */
  session: DraftSession | null
  /** 非空 = 成线像素对，集成层据此提交创建 */
  commit: [Point, Point] | null
}

function moved(start: Point, pt: Point): boolean {
  return Math.hypot(pt.x - start.x, pt.y - start.y) >= DRAG_COMMIT_THRESHOLD
}

/** 进入画线模式后的首次按下：双锚点工具开草稿，单锚点工具返回 null（走 click 提交） */
export function startDraft(tool: KlineDrawingType, pt: Point): DraftSession | null {
  if (!isTwoAnchorTool(tool)) return null
  return { tool, phase: 'pressing', startPx: pt, cursorPx: pt }
}

/** 指针移动：仅更新预览终点 */
export function moveDraft(draft: DraftSession, pt: Point): DraftTransition {
  return { session: { ...draft, cursorPx: pt }, commit: null }
}

/** 首锚点释放：位移达标直接成线（拖拽式），否则转入等待第二下（点击式） */
export function releaseDraft(draft: DraftSession, pt: Point): DraftTransition {
  if (moved(draft.startPx, pt)) return { session: null, commit: [draft.startPx, pt] }
  return { session: { ...draft, phase: 'awaitSecond', cursorPx: pt }, commit: null }
}

/** 等待第二下时的落点：成线并终结草稿 */
export function pressSecond(draft: DraftSession, pt: Point): DraftTransition {
  return { session: null, commit: [draft.startPx, pt] }
}
