/**
 * Agent Hub 贾维斯总览页（仅 admin，路由 /trading-agent index）：
 * 中心枢纽舞台（AgentHubStage——资源站 + Agent 单元 + 真实数据流连线，
 * 运行态由后端 runtime_state 判定）30s 轮询 /agents 聚合；点击 Agent 单元
 * 切换下方实时决策流，「进入工作台」才跳详情页；Agent 管理（含新建）收进
 * 默认折叠的 Collapse 面板（D32）。
 */
import { Collapse, Typography } from 'antd'
import { useState } from 'react'

import { useAgentOverview } from '@/hooks/useTradingAgent'

import { AgentHubStage } from './AgentHubStage'
import { AgentManageList } from './AgentManageList'
import { LiveDecisionFeed } from './LiveDecisionFeed'

const REFRESH_INTERVAL_MS = 30_000

export function AgentOverview() {
  const { data, isLoading } = useAgentOverview({ refetchInterval: REFRESH_INTERVAL_MS })
  const items = data?.items ?? []
  const activeCount = items.filter((item) => item.profile.status === 'active').length
  const [selectedKey, setSelectedKey] = useState<string | null>(null)

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
      <div className="overflow-x-auto">
        <div className="h-[540px] min-w-[680px] overflow-hidden rounded-xl border border-white/10 bg-white/[0.03] md:h-[620px]">
          <AgentHubStage
            items={items}
            isLoading={isLoading}
            selectedKey={selectedKey}
            onSelectAgent={setSelectedKey}
          />
        </div>
      </div>
      <LiveDecisionFeed items={items} isLoading={isLoading} selectedKey={selectedKey} />
      <Collapse
        ghost
        size="small"
        className="shrink-0 [&_.ant-collapse-content-box]:!px-0"
        items={[
          {
            key: 'manage',
            label: (
              <Typography.Text className="text-xs">
                Agent 管理（{items.length} 个 · {activeCount} 启用）
              </Typography.Text>
            ),
            children: <AgentManageList items={items} isLoading={isLoading} />,
          },
        ]}
      />
    </div>
  )
}
