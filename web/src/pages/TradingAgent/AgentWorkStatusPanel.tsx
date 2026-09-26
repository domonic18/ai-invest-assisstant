/**
 * 工作台右栏状态面板（D29）：一屏回答「agent 靠什么工作、什么时候干活、
 * 最近干了什么」。三卡——能力与技能（风格/策略/方法论基座/作业技能/模型/
 * 记忆计数）、自动化任务（cron + 频率 + 下次执行 + 最近运行）、近期活动。
 */
import {
  CheckCircleFilled,
  CloseCircleFilled,
  LoadingOutlined,
  MinusCircleFilled,
} from '@ant-design/icons'
import { Card, Skeleton, Tag, Tooltip, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import type {
  AgentActivityItem,
  AgentCadence,
  ApiAgentAutomationTask,
  ApiAgentCapabilityResponse,
} from '@ai-invest/shared'

import { useTradingAgentStatus } from '@/hooks/useTradingAgent'
import { formatRelativeTime } from '@/utils/formatters'

import { useAgentKey } from './agentKeyContext'

const LAST_STATUS_META: Record<string, { color: string; icon: ReactNode; text: string }> = {
  success: { color: '#52c41a', icon: <CheckCircleFilled />, text: '成功' },
  partial: { color: '#faad14', icon: <CheckCircleFilled />, text: '部分成功' },
  failed: { color: '#ff4d4f', icon: <CloseCircleFilled />, text: '失败' },
  skipped: { color: '#8c8c8c', icon: <MinusCircleFilled />, text: '跳过' },
  running: { color: '#1677ff', icon: <LoadingOutlined />, text: '运行中' },
  pending: { color: '#1677ff', icon: <LoadingOutlined />, text: '排队中' },
}

const CADENCE_LABEL: Record<AgentCadence, string> = {
  daily: '每日',
  weekly: '每周',
  monthly: '每月',
}

function CapabilityRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="text-xs">
      <div className="text-white/45">{label}</div>
      <div className="mt-0.5 text-white/85">{children}</div>
    </div>
  )
}

function CapabilityCard({ status }: { status: ApiAgentCapabilityResponse }) {
  const { profile, llmName, methodologySourceName, skillLabel, skillIsSharedDefault, memoryCounts } =
    status
  return (
    <Card size="small" title="能力与技能">
      <div className="space-y-2.5">
        {profile.styleDesc && (
          <CapabilityRow label="风格">
            <Tag color="geekblue" className="!mr-0">
              {profile.styleDesc}
            </Tag>
          </CapabilityRow>
        )}
        {profile.strategyDesc && (
          <CapabilityRow label="策略">
            <Typography.Paragraph
              type="secondary"
              className="!mb-0 text-xs"
              ellipsis={{ rows: 3, tooltip: profile.strategyDesc }}
            >
              {profile.strategyDesc}
            </Typography.Paragraph>
          </CapabilityRow>
        )}
        <CapabilityRow label="方法论基座">
          {methodologySourceName ?? (
            <span className="text-white/40">未绑定（可在账户与配置中选择知识库源）</span>
          )}
        </CapabilityRow>
        <CapabilityRow label="作业技能">
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <Tag color="purple" className="!mr-0">
              {skillLabel}
            </Tag>
            {skillIsSharedDefault && (
              <span className="text-white/40">共享默认技能包（可在技能广场配置专属）</span>
            )}
          </span>
        </CapabilityRow>
        <CapabilityRow label="模型">
          {llmName ?? <span className="text-white/40">平台默认模型</span>}
        </CapabilityRow>
        <CapabilityRow label="记忆（活跃）">
          <span className="flex flex-wrap gap-1.5">
            <Tag className="!mr-0">纪律 {memoryCounts.discipline}</Tag>
            <Tag className="!mr-0">方法 {memoryCounts.method}</Tag>
            <Tag className="!mr-0">教训 {memoryCounts.lesson}</Tag>
          </span>
        </CapabilityRow>
      </div>
    </Card>
  )
}

function AutomationRow({ task }: { task: ApiAgentAutomationTask }) {
  const meta = task.lastStatus
    ? (LAST_STATUS_META[task.lastStatus] ?? LAST_STATUS_META.skipped)
    : null
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5">
      <div className="flex items-center gap-2 text-xs">
        <Typography.Text strong className="text-xs">
          {task.label}
        </Typography.Text>
        {task.cadence && <Tag className="!mr-0">{CADENCE_LABEL[task.cadence]}</Tag>}
        <span className="ml-auto" />
        {task.taskActive ? (
          <Tag color="processing" className="!mr-0">
            启用
          </Tag>
        ) : (
          <Tag className="!mr-0">停用</Tag>
        )}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-white/50">
        {task.cron && <span className="font-mono">{task.cron}</span>}
        <span>下次 {task.nextRunAt ? formatRelativeTime(task.nextRunAt) : '—'}</span>
        {meta ? (
          <Tooltip title={meta.text}>
            <span className="inline-flex cursor-default items-center gap-1">
              <span style={{ color: meta.color, fontSize: 12 }}>{meta.icon}</span>
              最近 {task.lastRunAt ? formatRelativeTime(task.lastRunAt) : '—'}
            </span>
          </Tooltip>
        ) : (
          <span>最近 —</span>
        )}
      </div>
    </div>
  )
}

function AutomationCard({ tasks }: { tasks: ApiAgentAutomationTask[] }) {
  return (
    <Card size="small" title="自动化任务">
      <div className="space-y-2">
        {tasks.map((task) => (
          <AutomationRow key={task.key} task={task} />
        ))}
      </div>
    </Card>
  )
}

function ActivityCard({ items }: { items: AgentActivityItem[] }) {
  return (
    <Card size="small" title="近期活动">
      {items.length === 0 ? (
        <Typography.Text type="secondary" className="text-xs">
          暂无活动
        </Typography.Text>
      ) : (
        <div className="space-y-1.5">
          {items.slice(0, 5).map((item, idx) => (
            <div
              key={`${item.kind}-${item.occurredAt ?? ''}-${idx}`}
              className="flex items-baseline gap-2 text-xs"
            >
              <span className="shrink-0 text-white/85">{item.title}</span>
              {item.stockCode && (
                <Link to={`/stock/${item.stockCode}`} className="min-w-0 flex-1 truncate">
                  <Tag className="!m-0 !text-xs">
                    {item.stockName ?? item.stockCode}
                    <span className="ml-1 font-mono text-white/40">{item.stockCode}</span>
                  </Tag>
                </Link>
              )}
              {!item.stockCode && <span className="min-w-0 flex-1 truncate text-white/50">{item.detail}</span>}
              {item.occurredAt && (
                <span className="shrink-0 text-white/40">{formatRelativeTime(item.occurredAt)}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

export function AgentWorkStatusPanel() {
  const agentKey = useAgentKey()
  const { data: status, isLoading } = useTradingAgentStatus(agentKey)

  if (isLoading || !status) {
    return (
      <Card size="small" title="工作状态">
        <Skeleton active title={false} paragraph={{ rows: 10 }} />
      </Card>
    )
  }
  return (
    <>
      <CapabilityCard status={status} />
      <AutomationCard tasks={status.automation} />
      <ActivityCard items={status.recentActivity} />
    </>
  )
}
