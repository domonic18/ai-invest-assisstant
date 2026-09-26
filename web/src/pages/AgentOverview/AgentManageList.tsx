/**
 * Agent 管理列表（总览页底部，D28）：列出全部注册 Agent（含
 * planned/disabled），状态 Badge + 启用 Switch（停用 = 雷达隐藏且不参与
 * 调度）+「详情」入口；任意状态可进配置页编辑人设/频率/风控。
 */
import { Badge, Button, Card, Popconfirm, Space, Spin, Switch, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

import type { AgentOverviewItem } from '@ai-invest/shared'

import { useUpdateTradingAgentConfig } from '@/hooks/useTradingAgent'

const STATUS_META = {
  active: { text: '启用中', color: 'processing' },
  planned: { text: '未上线', color: 'warning' },
  disabled: { text: '已停用', color: 'default' },
} as const

function ManageRow({ item }: { item: AgentOverviewItem }) {
  const navigate = useNavigate()
  const { profile } = item
  const update = useUpdateTradingAgentConfig(profile.agentKey)
  const meta = STATUS_META[profile.status]

  const toggle = (next: boolean) => {
    update.mutate({ status: next ? 'active' : 'disabled' })
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <Badge status={meta.color} text={<Typography.Text className="text-xs">{meta.text}</Typography.Text>} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <Typography.Text strong className="text-xs">
            {profile.name}
          </Typography.Text>
          <Typography.Text type="secondary" className="font-mono text-xs">
            {profile.agentKey}
          </Typography.Text>
        </div>
        <Typography.Paragraph type="secondary" className="!mb-0 truncate text-xs">
          {profile.tagline}
        </Typography.Paragraph>
      </div>
      <Space size="small">
        <Popconfirm
          title={profile.status === 'active' ? '停用该 Agent？' : '启用该 Agent？'}
          description={
            profile.status === 'active'
              ? '停用后雷达图不再显示，且不参与计划/复盘调度。'
              : '启用后出现在总览雷达并按计划/复盘频率参与调度。'
          }
          okText={profile.status === 'active' ? '停用' : '启用'}
          cancelText="取消"
          onConfirm={() => toggle(profile.status !== 'active')}
        >
          <Switch
            size="small"
            checked={profile.status === 'active'}
            loading={update.isPending}
            checkedChildren="启用"
            unCheckedChildren="停用"
          />
        </Popconfirm>
        <Button size="small" onClick={() => void navigate(`/trading-agent/${profile.agentKey}`)}>
          详情
        </Button>
      </Space>
    </div>
  )
}

export function AgentManageList({
  items,
  isLoading,
}: {
  items: AgentOverviewItem[]
  isLoading: boolean
}) {
  return (
    <Card size="small" title="Agent 管理列表" className="shrink-0">
      {isLoading ? (
        <div className="flex justify-center py-4">
          <Spin size="small" />
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <ManageRow key={item.profile.agentKey} item={item} />
          ))}
        </div>
      )}
    </Card>
  )
}
