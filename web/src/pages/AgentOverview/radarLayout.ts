/**
 * 雷达节点布局（纯函数）：仅 active Agent（D28——planned/disabled 一律隐藏，
 * 管理入口在总览页「Agent 管理列表」）。像素坐标椭圆轨道（rx=0.36W、
 * ry=0.32H），Canvas 与 HTML 标签覆盖层共用同一份几何，节点位置 clamp 在
 * 容器内边距内，杜绝越界裁剪（修复单节点 -90° 出界与宽画布双层错位）。
 */
import type { AgentOverviewItem } from '@ai-invest/shared'

export interface RadarNode {
  agentKey: string
  name: string
  accentColor: string
  busy: boolean
  /** 像素坐标（相对容器左上角，Canvas CSS 像素与 HTML absolute 同基准）。 */
  x: number
  y: number
}

/** 椭圆轨道半径（相对容器宽/高）。 */
const ORBIT_RX = 0.36
const ORBIT_RY = 0.32
/** 节点卡半宽余量：clamp 保证锚点不贴边（节点卡 translate(-50%,-50%)）。 */
const EDGE_PAD = 72

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export function layoutRadarNodes(
  items: AgentOverviewItem[],
  width: number,
  height: number,
): RadarNode[] {
  if (width <= 0 || height <= 0) return []
  const active = items.filter((item) => item.profile.status === 'active')
  const cx = width / 2
  const cy = height / 2

  return active.map((item, i) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / active.length
    return {
      agentKey: item.profile.agentKey,
      name: item.profile.name,
      accentColor: item.profile.accentColor,
      busy: true,
      x: clamp(cx + ORBIT_RX * width * Math.cos(angle), EDGE_PAD, width - EDGE_PAD),
      y: clamp(cy + ORBIT_RY * height * Math.sin(angle), EDGE_PAD, height - EDGE_PAD),
    }
  })
}
