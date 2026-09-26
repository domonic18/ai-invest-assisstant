/**
 * Agent Hub 舞台布局纯函数（D32）：中心枢纽（模拟盘交易系统）+ 中环资源站 +
 * 外环 Agent 单元。三层渲染（Canvas 背景 / SVG 边 / HTML 节点）共用同一份
 * 布局输出与容器尺寸（ResizeObserver 实测），杜绝层间错位。
 */

export type StationId = 'kb' | 'review' | 'news' | 'sentiment' | 'paper'

/** 中环资源站排布顺序（paper 独占中心枢纽，不入环）。 */
export const RING_STATIONS: StationId[] = ['kb', 'review', 'news', 'sentiment']

export interface Point {
  x: number
  y: number
}

export interface HubLayout {
  center: Point
  stations: Record<StationId, Point>
  agents: Point[]
}

/** 节点不越容器边界的最小内边距（px）。 */
const CLAMP_MARGIN = 52

function clampPoint(p: Point, width: number, height: number): Point {
  const maxX = Math.max(CLAMP_MARGIN, width - CLAMP_MARGIN)
  const maxY = Math.max(CLAMP_MARGIN, height - CLAMP_MARGIN)
  return {
    x: Math.min(Math.max(p.x, CLAMP_MARGIN), maxX),
    y: Math.min(Math.max(p.y, CLAMP_MARGIN), maxY),
  }
}

function polar(center: Point, r: number, angle: number): Point {
  return { x: center.x + r * Math.cos(angle), y: center.y + r * Math.sin(angle) }
}

/**
 * 计算舞台全部节点像素坐标。
 *
 * - 中心枢纽 paper 固定在容器中心；
 * - 中环 4 资源站自顶部起均匀角度，半径 min(0.22W, 0.30H)；
 * - 外环 Agent 槽位 SLOTS=max(agentCount, 8) 均匀角度，半径
 *   min(0.38W, 0.46H)；agentCount > 8 时奇偶槽双半径交替（0.84×）防重叠。
 */
export function layoutHub(width: number, height: number, agentCount: number): HubLayout {
  const center = { x: width / 2, y: height / 2 }
  const stationR = Math.min(width * 0.22, height * 0.3)
  const stations = { paper: { ...center } } as Record<StationId, Point>
  RING_STATIONS.forEach((id, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / RING_STATIONS.length
    stations[id] = clampPoint(polar(center, stationR, angle), width, height)
  })

  const count = Math.max(agentCount, 0)
  const slots = Math.max(count, 8)
  const baseR = Math.min(width * 0.38, height * 0.46)
  const agents: Point[] = []
  for (let i = 0; i < count; i++) {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / slots
    const r = slots > 8 && i % 2 === 1 ? baseR * 0.84 : baseR
    agents.push(clampPoint(polar(center, r, angle), width, height))
  }
  return { center, stations, agents }
}
