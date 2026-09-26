/**
 * Agent Hub 贾维斯总览页（仅 admin，路由 /trading-agent index）：
 * 中心市场核心 + 轨道 Agent 节点的雷达 HUD（Canvas 2D），30s 轮询
 * /agents 聚合；仅显示 active 节点（D28），点击进详情；雷达容器实测
 * 宽高（ResizeObserver）驱动 radarLayout 像素几何，Canvas 与标签层共用；
 * 底部活动时间轴 + Agent 管理列表。
 */
import { Empty, Typography } from 'antd'
import { useEffect, useRef, useState } from 'react'

import { useAgentOverview } from '@/hooks/useTradingAgent'

import { AgentRadarCanvas } from './AgentRadarCanvas'
import { AgentNodeLabels } from './AgentNodeLabels'
import { ActivityTimeline } from './ActivityTimeline'
import { layoutRadarNodes } from './radarLayout'
import { AgentManageList } from './AgentManageList'

const REFRESH_INTERVAL_MS = 30_000

interface RadarDims {
  width: number
  height: number
}

export function AgentOverview() {
  const { data, isLoading } = useAgentOverview({ refetchInterval: REFRESH_INTERVAL_MS })
  const items = data?.items ?? []
  const radarRef = useRef<HTMLDivElement>(null)
  const [dims, setDims] = useState<RadarDims>({ width: 0, height: 0 })

  useEffect(() => {
    const el = radarRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect
      if (rect) setDims({ width: rect.width, height: rect.height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const nodes = layoutRadarNodes(items, dims.width, dims.height)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex shrink-0 items-baseline gap-3">
        <Typography.Title level={4} className="!mb-0">
          Agent Hub
        </Typography.Title>
        <Typography.Text type="secondary" className="text-xs">
          交易 Agent 总览 · 每 30 秒自动刷新
        </Typography.Text>
      </div>
      <div
        ref={radarRef}
        className="relative h-[400px] overflow-hidden rounded-xl border border-white/10 bg-white/[0.03] md:h-[480px]"
      >
        <AgentRadarCanvas nodes={nodes} />
        <AgentNodeLabels nodes={nodes} />
        {!isLoading && items.length > 0 && nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Empty description="暂无启用的 Agent" />
          </div>
        )}
      </div>
      <ActivityTimeline items={items} isLoading={isLoading} generatedAt={data?.generatedAt} />
      <AgentManageList items={items} isLoading={isLoading} />
    </div>
  )
}
