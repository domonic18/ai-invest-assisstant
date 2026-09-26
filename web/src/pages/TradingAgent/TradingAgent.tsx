/**
 * Agent 详情页（仅 admin，路由 /trading-agent/:agentKey）：单 Agent 闭环统一入口。
 *
 * 结构 = 运行状态条 + Tabs：工作台（agent 对话，PC 附工作状态侧栏）、
 * Agent 自选（选股清单 + 人工移出）、持仓与交易（agent 账户资金/持仓/
 * 委托/成交）、交易计划、复盘记录（日/周/月）、经验总结（分层复盘 +
 * Agent 记忆管理）、配置（基本配置 + 会话人设 + 作业技能 + 模拟盘账户，
 * D30 四区）。tab 态进 URL query；
 * 工作台保持挂载（antd Tabs 默认隐藏不卸载），切 tab 不中断会话流。
 */
import { EditOutlined } from '@ant-design/icons'
import { Button, Spin, Tabs, Tag, Typography } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PAGE_EVENT_TYPES } from '@ai-invest/shared'
import type { TradingAgentProfile } from '@ai-invest/shared'

import { useAssistantSessions } from '@/components/assistant/hooks/useAssistantSessions'
import { AssistantErrorBoundary } from '@/components/assistant/AssistantErrorBoundary'
import { AssistantRuntimeProvider } from '@/components/assistant/AssistantRuntimeProvider'
import { AssistantSidebar } from '@/components/assistant/AssistantSidebar'
import { AssistantThread } from '@/components/assistant/AssistantThread'
import { TodoListBar } from '@/components/assistant/ui/TodoListBar'
import { queryKeys } from '@/hooks/queryKeys'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useTradingAgentConfig, useTradingAgentLlmOptions, useTradingAgentStatus } from '@/hooks/useTradingAgent'
import { useAssistantStore } from '@/stores/assistant'

import { AgentKeyContext, useAgentKey } from './agentKeyContext'

import { AgentConfigPanel } from './AgentConfigPanel'
import { AgentPersonaPanel } from './AgentPersonaPanel'
import { AgentSkillPanel } from './AgentSkillPanel'
import { AgentWorkStatusPanel } from './AgentWorkStatusPanel'
import { AgentMemoryPanel } from './AgentMemoryPanel'
import { AgentSelectionsPanel } from './AgentSelectionsPanel'
import { AgentStatusStrip } from './AgentStatusStrip'
import { AgentTradeRecords } from './AgentTradeRecords'
import { ExperiencePanel } from './ExperiencePanel'
import { PaperTradeAccountsAdmin } from '@/pages/Admin/PaperTradeAccounts'
import { PlanPanel } from './PlanPanel'
import { ReviewPanel } from './ReviewPanel'

const TAB_KEYS = [
  'workbench',
  'selections',
  'records',
  'plans',
  'review',
  'experiences',
  'config',
] as const
type TabKey = (typeof TAB_KEYS)[number]

const TAB_ITEMS = [
  { key: 'workbench', label: '工作台' },
  { key: 'selections', label: 'Agent 自选' },
  { key: 'records', label: '持仓与交易' },
  { key: 'plans', label: '交易计划' },
  { key: 'review', label: '复盘记录' },
  { key: 'experiences', label: '经验总结' },
  { key: 'config', label: '配置' },
]

function renderTabPane(key: TabKey) {
  switch (key) {
    case 'workbench':
      return <WorkbenchPane />
    case 'selections':
      return <AgentSelectionsPanel />
    case 'records':
      return <AgentTradeRecords />
    case 'plans':
      return <PlanPanel />
    case 'review':
      return <ReviewPanel />
    case 'experiences':
      return (
        <div className="space-y-3">
          <ExperiencePanel />
          <AgentMemoryPanel />
        </div>
      )
    case 'config':
      return (
        <div className="space-y-3">
          <AgentConfigPanel />
          <AgentPersonaPanel />
          <AgentSkillPanel />
          <PaperTradeAccountsAdmin />
        </div>
      )
  }
}

function TradingChatHeader({ onNewThread }: { onNewThread: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
      <div className="min-w-0">
        <Typography.Text strong>交易 Agent</Typography.Text>
        <Typography.Text type="secondary" className="ml-2 text-xs">
          绑定专属模拟盘账户 · 下单/撤单前会与你确认
        </Typography.Text>
      </div>
      <Button size="small" icon={<EditOutlined />} onClick={onNewThread}>
        新会话
      </Button>
    </div>
  )
}

function WorkbenchPane() {
  const agentKey = useAgentKey()
  const [threadId, setThreadId] = useState<string | undefined>(undefined)
  const lastThreadIdRef = useRef<string | undefined>(undefined)
  const todos = useAssistantStore((state) => state.todos)
  const { sessions, isLoading, deleteSessionById, refresh } = useAssistantSessions({
    agentType: agentKey,
  })

  // 线程变更单点：新会话首条消息发出后线程才真实创建（onThreadIdChange 回填），
  // 创建/切换时刷新会话列表（ref 守卫避免渲染期 effect 反复 invalidate）
  const changeThread = (id: string | undefined) => {
    if (id === lastThreadIdRef.current) return
    lastThreadIdRef.current = id
    setThreadId(id)
    if (id) refresh()
  }

  const handleDelete = async (id: string) => {
    await deleteSessionById(id)
    if (id === threadId) changeThread(undefined)
  }

  return (
    <div className="flex h-[calc(100dvh-13.5rem)] min-h-[420px] gap-3">
      <div className="hidden shrink-0 md:block">
        <AssistantSidebar
          sessions={sessions}
          activeThreadId={threadId}
          isLoading={isLoading}
          width={240}
          onNewThread={() => changeThread(undefined)}
          onSwitchThread={changeThread}
          onDeleteThread={handleDelete}
        />
      </div>
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
        <TradingChatHeader onNewThread={() => changeThread(undefined)} />
        {todos && todos.length > 0 && <TodoListBar todos={todos} />}
        <div className="min-h-0 flex-1">
          <AssistantErrorBoundary>
            <AssistantRuntimeProvider
              agentType={agentKey}
              threadId={threadId}
              onThreadIdChange={changeThread}
            >
              <AssistantThread />
            </AssistantRuntimeProvider>
          </AssistantErrorBoundary>
        </div>
      </div>
      <div className="hidden w-[320px] shrink-0 space-y-3 overflow-y-auto lg:block">
        <AgentWorkStatusPanel />
      </div>
    </div>
  )
}

/** Agent 介绍卡：accent_color 点缀 + 策略/风格/方法论/模型（注册行 + 能力视图）。 */
function AgentIntroCard({ profile }: { profile: TradingAgentProfile }) {
  const { data: llmOptions } = useTradingAgentLlmOptions()
  const { data: capability } = useTradingAgentStatus(profile.agentKey)
  const llmName = profile.llmConfigId
    ? llmOptions?.find((option) => option.value === profile.llmConfigId)?.label
    : '平台默认模型'

  return (
    <div className="flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1.5 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5">
      <span className="inline-flex items-center gap-2">
        <span
          className="inline-block size-2.5 rounded-full"
          style={{ backgroundColor: profile.accentColor }}
        />
        <Typography.Text strong>{profile.name}</Typography.Text>
        {profile.tagline ? (
          <Typography.Text type="secondary" className="text-xs">
            {profile.tagline}
          </Typography.Text>
        ) : null}
      </span>
      {profile.strategyDesc ? (
        <span className="inline-flex items-center gap-1.5 text-xs">
          <span className="text-white/60">策略</span>
          <Typography.Text className="text-xs">{profile.strategyDesc}</Typography.Text>
        </span>
      ) : null}
      {profile.styleDesc ? (
        <span className="inline-flex items-center gap-1.5 text-xs">
          <span className="text-white/60">风格</span>
          <Tag color="geekblue" className="!mr-0">
            {profile.styleDesc}
          </Tag>
        </span>
      ) : null}
      <span className="inline-flex items-center gap-1.5 text-xs">
        <span className="text-white/60">方法论</span>
        <Tag color="purple" className="!mr-0">
          {capability?.methodologySourceName ?? '未绑定'}
        </Tag>
      </span>
      <span className="inline-flex items-center gap-1.5 text-xs">
        <span className="text-white/60">模型</span>
        <Typography.Text className="text-xs">{llmName ?? '…'}</Typography.Text>
      </span>
      <span className="inline-flex items-center gap-1.5 text-xs">
        <span className="text-white/60">风控</span>
        <Typography.Text className="text-xs">
          单票 ≤{profile.riskMaxPositionPct}% · 总仓 ≤{profile.riskMaxTotalPct}% · 日委托 ≤
          {profile.riskMaxDailyOrders}笔
        </Typography.Text>
      </span>
    </div>
  )
}

export function TradingAgent() {
  const { agentKey } = useParams()
  const navigate = useNavigate()

  // 注册表驱动路由参数；缺参（/trading-agent/）回总览页，不做键名兜底
  useEffect(() => {
    if (!agentKey) navigate('/trading-agent', { replace: true })
  }, [agentKey, navigate])

  const { data: profile, isLoading: profileLoading } = useTradingAgentConfig(agentKey ?? '')
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()

  // Agent 委托/计划成功事件：刷新模拟盘数据与交易计划，事件即消费
  usePageAssistantResult(PAGE_EVENT_TYPES.paperTrading, () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.all })
    return true
  })

  const rawTab = searchParams.get('tab') ?? 'workbench'
  const activeTab: TabKey = (TAB_KEYS as readonly string[]).includes(rawTab)
    ? (rawTab as TabKey)
    : 'workbench'
  const changeTab = (key: string) => {
    setSearchParams((prev) => {
      prev.set('tab', key)
      return prev
    }, { replace: true })
  }

  return (
    <AgentKeyContext.Provider value={agentKey ?? null}>
      <div className="flex h-[calc(100dvh-5.75rem)] min-h-[480px] flex-col gap-3 md:h-[calc(100dvh-6.5rem)]">
        {profile ? (
          <AgentIntroCard profile={profile} />
        ) : profileLoading ? (
          <div className="flex shrink-0 justify-center py-2">
            <Spin size="small" />
          </div>
        ) : null}
        <AgentStatusStrip onOpenAccounts={() => changeTab('config')} />
        <div className="min-h-0 flex-1">
          <Tabs
            activeKey={activeTab}
            onChange={changeTab}
            items={TAB_ITEMS.map((item) => ({ ...item, children: renderTabPane(item.key as TabKey) }))}
            size="small"
            className="flex h-full flex-col [&_.ant-tabs-content-holder]:min-h-0 [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-content-holder]:overflow-y-auto [&_.ant-tabs-nav]:!mb-3 [&_.ant-tabs-nav]:shrink-0 [&_.ant-tabs-tab]:!py-1.5"
            destroyInactiveTabPane={false}
          />
        </div>
      </div>
    </AgentKeyContext.Provider>
  )
}
