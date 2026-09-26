/**
 * Agent Hub 舞台分层布局纯函数（D33）：自上而下三层——Agent 运行层 /
 * 资源系统层（五站同维度，paper 不再特殊化）/ 基建层（状态灯五盒 +
 * Celery 队列分组任务方框）。三层渲染（Canvas 背景 / SVG 边 / HTML 节点）
 * 共用同一份布局输出与容器实测尺寸，杜绝层间错位。
 */

export type StationId = 'kb' | 'review' | 'news' | 'sentiment' | 'paper'

/** 资源系统层排布顺序（五站同维度均布）。 */
export const RING_STATIONS: StationId[] = ['kb', 'review', 'news', 'sentiment', 'paper']

/** 基建层五项核心（system status key 映射见 AgentHubStage）。 */
export type InfraId = 'postgres' | 'redis' | 'celery' | 'counter' | 'minio'

export const INFRA_IDS: InfraId[] = ['postgres', 'redis', 'celery', 'counter', 'minio']

export interface Point {
  x: number
  y: number
}

export interface LayerLayout {
  agents: Point[]
  stations: Record<StationId, Point>
  infra: Record<InfraId, Point>
  /** Celery 队列分组锚点（每队列一个，与 celery-queues.queues 一一对应）。 */
  queues: Point[]
}

/** 各层纵向位置（容器高度比例）。 */
const BAND_Y = { agents: 0.16, stations: 0.46, infra: 0.74, queues: 0.92 }

/** 节点不越容器边界的最小内边距（px）。 */
const CLAMP_MARGIN = 56

function clampPoint(p: Point, width: number, height: number): Point {
  const maxX = Math.max(CLAMP_MARGIN, width - CLAMP_MARGIN)
  const maxY = Math.max(CLAMP_MARGIN, height - CLAMP_MARGIN)
  return {
    x: Math.min(Math.max(p.x, CLAMP_MARGIN), maxX),
    y: Math.min(Math.max(p.y, CLAMP_MARGIN), maxY),
  }
}

/** 一行 n 个节点在条带内均布的横坐标（间距 = width/(n+1)）。 */
function rowPoints(count: number, y: number, width: number): Point[] {
  return Array.from({ length: count }, (_, i) => ({
    x: (width * (i + 1)) / (count + 1),
    y,
  }))
}

/**
 * 计算分层舞台全部节点像素坐标。
 *
 * - Agent 层：agentCount 个单元单行均布（0 个时返回空数组）；
 * - 资源系统层：五站同维度均布；
 * - 基建层：五盒均布；底带按 queueCount（Celery 队列数）均布分组锚点。
 */
export function layoutLayers(
  width: number,
  height: number,
  agentCount: number,
  queueCount: number,
): LayerLayout {
  const agents = rowPoints(Math.max(agentCount, 0), height * BAND_Y.agents, width).map((p) =>
    clampPoint(p, width, height),
  )
  const stations = {} as Record<StationId, Point>
  rowPoints(RING_STATIONS.length, height * BAND_Y.stations, width).forEach((p, i) => {
    stations[RING_STATIONS[i]] = clampPoint(p, width, height)
  })
  const infra = {} as Record<InfraId, Point>
  rowPoints(INFRA_IDS.length, height * BAND_Y.infra, width).forEach((p, i) => {
    infra[INFRA_IDS[i]] = clampPoint(p, width, height)
  })
  const queues = rowPoints(Math.max(queueCount, 0), height * BAND_Y.queues, width).map((p) =>
    clampPoint(p, width, height),
  )
  return { agents, stations, infra, queues }
}
