/**
 * Agent Hub 真实连线（D32）：只画配置绑定/数据流真实存在的边，装饰性连线
 * 一律不画。流向 = 数据被消费的方向——资讯/社交情绪汇入大盘复盘（上游），
 * 复盘数据作为计划输入流向 agent；知识库按 methodologySourceId 绑定连；
 * 模拟盘按专属账户绑定连。活跃度按 agent 最近活动时间衰减分档。
 */
import type { AgentOverviewItem } from '@ai-invest/shared'

import type { StationId } from './hubLayout'

export type EdgeKind = 'plan-input' | 'methodology' | 'account' | 'upstream'
export type EdgeSpeed = 'fast' | 'slow' | 'still'

export interface HubEdge {
  id: string
  from: StationId
  /** 目标 agent_key；站间上游边为 null。 */
  toAgent: string | null
  kind: EdgeKind
  speed: EdgeSpeed
  opacity: number
}

const MINUTE_MS = 60_000

/** 按最近活动时间分档：<30min 快速流光 / <6h 慢速 / 更久静态弱线。 */
export function edgeDecay(lastActiveAt?: string | null): { speed: EdgeSpeed; opacity: number } {
  if (!lastActiveAt) return { speed: 'still', opacity: 0.18 }
  const age = Date.now() - new Date(lastActiveAt).getTime()
  if (age < 30 * MINUTE_MS) return { speed: 'fast', opacity: 0.9 }
  if (age < 6 * 60 * MINUTE_MS) return { speed: 'slow', opacity: 0.5 }
  return { speed: 'still', opacity: 0.18 }
}

/** 由总览聚合推导全部真实连线（未启用 agent 占位不连）。 */
export function buildHubEdges(items: AgentOverviewItem[]): HubEdge[] {
  const edges: HubEdge[] = []
  let latestReviewAt: string | null = null
  for (const item of items) {
    const { profile } = item
    if (profile.status !== 'active') continue
    const { speed, opacity } = edgeDecay(item.recentActivity[0]?.occurredAt)
    edges.push({
      id: `review->${profile.agentKey}`,
      from: 'review',
      toAgent: profile.agentKey,
      kind: 'plan-input',
      speed,
      opacity,
    })
    if (profile.methodologySourceId != null) {
      edges.push({
        id: `kb->${profile.agentKey}`,
        from: 'kb',
        toAgent: profile.agentKey,
        kind: 'methodology',
        speed,
        opacity,
      })
    }
    if (item.accountName) {
      edges.push({
        id: `paper->${profile.agentKey}`,
        from: 'paper',
        toAgent: profile.agentKey,
        kind: 'account',
        speed,
        opacity,
      })
    }
    const reviewAt =
      item.recentActivity.find((activity) => activity.kind === 'review')?.occurredAt ??
      null
    if (reviewAt && (!latestReviewAt || reviewAt > latestReviewAt)) {
      latestReviewAt = reviewAt
    }
  }
  // 站间上游：资讯中心 / 大V情绪 → 复盘数据（大盘复盘引用二者，间接进计划）
  for (const from of ['news', 'sentiment'] as StationId[]) {
    const decay = edgeDecay(latestReviewAt)
    edges.push({
      id: `${from}->review`,
      from,
      toAgent: null,
      kind: 'upstream',
      speed: decay.speed,
      opacity: decay.opacity,
    })
  }
  return edges
}
