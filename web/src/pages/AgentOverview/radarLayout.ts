/**
 * 雷达节点布局（纯函数）：active Agent 均布外轨道，planned 幽灵节点内轨道。
 * 归一化坐标 (0..1)，画布与 HTML 标签覆盖层共用同一份几何。
 */
import type { AgentOverviewItem } from '@ai-invest/shared'

export interface RadarNode {
  agentKey: string
  name: string
  tagline: string
  strategyDesc: string
  accentColor: string
  /** planned 等未激活注册行：暗色幽灵节点，点击只弹简介卡。 */
  ghost: boolean
  /** active Agent：脉冲光环 + 数据粒子流。 */
  busy: boolean
  /** 轨道半径（0..1，相对画布短边半径）。 */
  radius: number
  /** 归一化画布坐标。 */
  x: number
  y: number
}

const ACTIVE_ORBIT = 0.62
const GHOST_ORBIT = 0.34

function polar(cx: number, cy: number, radius: number, angleDeg: number): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180
  return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) }
}

export function layoutRadarNodes(items: AgentOverviewItem[]): RadarNode[] {
  const cx = 0.5
  const cy = 0.5
  const active = items.filter((item) => item.profile.status === 'active')
  const planned = items.filter((item) => item.profile.status !== 'active')

  const toNode = (item: AgentOverviewItem, radius: number, angle: number): RadarNode => {
    const { x, y } = polar(cx, cy, radius, angle)
    return {
      agentKey: item.profile.agentKey,
      name: item.profile.name,
      tagline: item.profile.tagline,
      strategyDesc: item.profile.strategyDesc,
      accentColor: item.profile.accentColor,
      ghost: item.profile.status !== 'active',
      busy: item.profile.status === 'active',
      radius,
      x,
      y,
    }
  }

  // active 从正上方起均布；ghost 错开半个步长避免与 active 同角
  const activeNodes = active.map((item, i) =>
    toNode(item, ACTIVE_ORBIT, -90 + (360 / Math.max(active.length, 1)) * i),
  )
  const ghostNodes = planned.map((item, i) =>
    toNode(
      item,
      GHOST_ORBIT,
      -90 + (360 / Math.max(planned.length, 1)) * i + 180 / Math.max(planned.length, 1),
    ),
  )
  return [...activeNodes, ...ghostNodes]
}
