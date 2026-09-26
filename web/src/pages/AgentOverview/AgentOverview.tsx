/**
 * Agent Hub 贾维斯总览页（仅 admin，路由 /trading-agent index）：
 * 中心市场核心 + 轨道 Agent 节点的雷达 HUD（Canvas 2D），30s 轮询
 * /agents 聚合；点击 active 节点进详情，ghost 节点弹简介卡；
 * 底部活动时间轴回答「正在做 / 接下来做什么」。
 */
import { Typography } from 'antd'

import { useAgentOverview } from '@/hooks/useTradingAgent'

import { AgentRadarCanvas } from './AgentRadarCanvas'
import { AgentNodeLabels } from './AgentNodeLabels'
import { ActivityTimeline } from './ActivityTimeline'
import { layoutRadarNodes } from './radarLayout'

const REFRESH_INTERVAL_MS = 30_000

export function AgentOverview() {
  const { data, isLoading } = useAgentOverview({ refetchInterval: REFRESH_INTERVAL_MS })
  const items = data?.items ?? []
  const nodes = layoutRadarNodes(items)

  return (
    <div className="flex h-[calc(100dvh-5.75rem)] min-h-[560px] flex-col gap-3 md:h-[calc(100dvh-6.5rem)]">
      <div className="flex shrink-0 items-baseline gap-3">
        <Typography.Title level={4} className="!mb-0">
          Agent Hub
        </Typography.Title>
        <Typography.Text type="secondary" className="text-xs">
          交易 Agent 总览 · 每 30 秒自动刷新
        </Typography.Text>
      </div>
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
        <AgentRadarCanvas nodes={nodes} />
        <AgentNodeLabels nodes={nodes} />
      </div>
      <ActivityTimeline
        items={items}
        isLoading={isLoading}
        generatedAt={data?.generatedAt}
      />
    </div>
  )
}
