import type { ChainEdge, ChainNode } from '@ai-invest/shared'

export const NODE_TYPE_COLORS: Record<ChainNode['type'], string> = {
  upstream: '#58a6ff',
  midstream: '#5e6ad2',
  downstream: '#2ea043',
}

export const NODE_TYPE_LABELS: Record<ChainNode['type'], string> = {
  upstream: '上游',
  midstream: '中游',
  downstream: '下游',
}

const MARGIN_OPACITY_MIN = 0.12
const MARGIN_OPACITY_MAX = 0.45
const MARGIN_SCALE_CAP = 60

/** 毛利率(0-60%)映射为节点填充透明度(0.12-0.45)；null 返回 0.08 灰显。 */
export function marginToOpacity(margin: number | null): number {
  if (margin === null || Number.isNaN(margin)) return 0.08
  const clamped = Math.max(0, Math.min(MARGIN_SCALE_CAP, margin))
  const ratio = clamped / MARGIN_SCALE_CAP
  return MARGIN_OPACITY_MIN + ratio * (MARGIN_OPACITY_MAX - MARGIN_OPACITY_MIN)
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

/** criticality 映射边样式：high 实线主题色 / medium 灰蓝实线 / low|null 灰色虚线。 */
export function edgeStyleByCriticality(
  criticality: ChainEdge['criticality'],
): EdgeVisualStyle {
  switch (criticality) {
    case 'high':
      return { stroke: '#5e6ad2' }
    case 'medium':
      return { stroke: '#7c8bb5' }
    default:
      return { stroke: '#6b7280', lineDash: [6, 4] }
  }
}
