/**
 * Agent 管理列表（总览页底部，D28 + D29）：列出全部注册 Agent（含
 * planned/disabled），状态 Badge + 启用 Switch +「详情」入口 + 删除；
 * D29 新增「新建 Agent」入口（创建即 active）与行级删除（级联清理）。
 */
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { Badge, Button, Card, Popconfirm, Space, Spin, Switch, Typography } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { AgentOverviewItem } from '@ai-invest/shared'

import { useDeleteTradingAgent, useUpdateTradingAgentConfig } from '@/hooks/useTradingAgent'

import { AgentCreateModal } from './AgentCreateModal'

const STATUS_META = {
  active: { text: '启用中', color: 'processing' },
  planned: { text: '未上线', color: 'warning' },
  disabled: { text: '已停用', color: 'default' },
} as const

function ManageRow({ item }: { item: AgentOverviewItem }) {
  const navigate = useNavigate()
  const { profile } = item
  const update = useUpdateTradingAgentConfig(profile.agentKey)
  const remove = useDeleteTradingAgent()
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
          cancelText="返回"
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
        <Popconfirm
          title={`删除 ${profile.name}？`}
          description="将解绑其模拟盘账户（账户保留），并删除该 Agent 的交易计划、选股、记忆与全部会话，不可恢复。"
          okText="删除"
          okButtonProps={{ danger: true }}
          cancelText="返回"
          onConfirm={() => remove.mutate(profile.agentKey)}
        >
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            loading={remove.isPending && remove.variables === profile.agentKey}
          />
        </Popconfirm>
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
  const [createOpen, setCreateOpen] = useState(false)
  return (
    <Card
      size="small"
      title="Agent 管理列表"
      className="shrink-0"
      extra={
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建 Agent
        </Button>
      }
    >
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
      <AgentCreateModal open={createOpen} onCancel={() => setCreateOpen(false)} />
    </Card>
  )
}
