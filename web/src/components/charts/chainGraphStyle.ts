import type { ChainEdge, ChainNode } from '@ai-invest/shared'

/** 节点类型描边/标题色（对齐原型图配色，用于浅色画布）。 */
export const NODE_TYPE_COLORS: Record<ChainNode['type'], string> = {
  upstream: '#3b82f6',
  midstream: '#6366f1',
  downstream: '#10b981',
}

export const NODE_TYPE_LABELS: Record<ChainNode['type'], string> = {
  upstream: '上游 — 原材料与零部件',
  midstream: '中游 — 制造与集成',
  downstream: '下游 — 应用与终端',
}

/** 分栏标题条的底色与文字色（深色画布版本）。 */
export const BAND_STYLES: Record<ChainNode['type'], { fill: string; text: string }> = {
  upstream: { fill: 'rgba(59,130,246,0.12)', text: '#3b82f6' },
  midstream: { fill: 'rgba(99,102,241,0.12)', text: '#6366f1' },
  downstream: { fill: 'rgba(16,185,129,0.12)', text: '#10b981' },
}

const BARRIER_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

/** 技术壁垒中文标签，null/未知返回 —。 */
export function techBarrierLabel(barrier: string | null): string {
  return (barrier && BARRIER_LABELS[barrier]) || '—'
}

/** 壁垒越高越醒目：high 红 / medium 琥珀 / low|null 灰。 */
export function techBarrierColor(barrier: string | null): string {
  switch (barrier) {
    case 'high':
      return '#ef4444'
    case 'medium':
      return '#d29922'
    default:
      return '#6b7280'
  }
}

/** 关联强度(0-100)映射为边线宽(1-5px)。 */
export function strengthToLineWidth(strength: number | null | undefined): number {
  if (strength === null || strength === undefined || Number.isNaN(strength)) return 1
  const clamped = Math.max(0, Math.min(100, strength))
  return 1 + (clamped / 100) * 4
}

export interface EdgeVisualStyle {
  stroke: string
  lineDash?: [number, number]
}

/** criticality 映射边样式：high 主题色实线 / medium 灰实线 / low|null 浅灰虚线。 */
export function edgeStyleByCriticality(
  criticality: ChainEdge['criticality'],
): EdgeVisualStyle {
  switch (criticality) {
    case 'high':
      return { stroke: '#6366f1' }
    case 'medium':
      return { stroke: '#9ca3af' }
    default:
      return { stroke: 'rgba(255,255,255,0.2)', lineDash: [6, 4] }
  }
}

export interface SignalBadge {
  icon: string
  text: string
  fill: string
  textFill: string
}

/** 组装节点底部的信号徽章：⚡ 技术突破（红）优先，⚠ 瓶颈（琥珀）补充，最多 maxCount 个。 */
export function buildSignalBadges(node: ChainNode, maxCount = 2): SignalBadge[] {
  const badges: SignalBadge[] = node.recentBreakthroughs.map((text) => ({
    icon: '⚡',
    text,
    fill: 'rgba(239,68,68,0.12)',
    textFill: '#ef4444',
  }))
  for (const text of node.bottleneckIndicators) {
    if (badges.length >= maxCount) break
    badges.push({ icon: '⚠', text, fill: 'rgba(217,153,34,0.12)', textFill: '#d29922' })
  }
  return badges.slice(0, maxCount)
}

export function truncateLabel(text: string, maxChars: number): string {
  return text.length > maxChars ? `${text.slice(0, maxChars - 1)}…` : text
}
