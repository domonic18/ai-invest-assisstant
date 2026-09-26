/**
 * 模拟管理页（原交易 Agent 页，仅 admin）：模拟盘闭环统一入口。
 *
 * 结构 = 运行状态条 + Tabs：工作台（agent 对话，PC 附计划/复盘侧栏）、
 * Agent 自选（选股清单 + 人工移出）、交易计划、交易记录（agent 账户
 * 委托/成交）、复盘记录（日/周/月）、经验总结（分层复盘 + Agent 记忆
 * 管理）、账户与配置（Agent 配置 + 模拟盘账户管理）。tab 态进 URL query（/admin/paper-trade 旧路由重定向
 * 到 ?tab=accounts）；工作台保持挂载（antd Tabs 默认隐藏不卸载），切 tab
 * 不中断会话流。
 */
import { EditOutlined } from '@ant-design/icons'
import { Button, Tabs, Typography } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { PAGE_EVENT_TYPES } from '@ai-invest/shared'

import { useAssistantSessions } from '@/components/assistant/hooks/useAssistantSessions'
import { AssistantErrorBoundary } from '@/components/assistant/AssistantErrorBoundary'
import { AssistantRuntimeProvider } from '@/components/assistant/AssistantRuntimeProvider'
import { AssistantSidebar } from '@/components/assistant/AssistantSidebar'
import { AssistantThread } from '@/components/assistant/AssistantThread'
import { TodoListBar } from '@/components/assistant/ui/TodoListBar'
import { queryKeys } from '@/hooks/queryKeys'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useAssistantStore } from '@/stores/assistant'

import { AgentConfigPanel } from './AgentConfigPanel'
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
  'plans',
  'records',
  'review',
  'experiences',
  'accounts',
] as const
type TabKey = (typeof TAB_KEYS)[number]

const TAB_ITEMS = [
  { key: 'workbench', label: '工作台' },
  { key: 'selections', label: 'Agent 自选' },
  { key: 'plans', label: '交易计划' },
  { key: 'records', label: '交易记录' },
  { key: 'review', label: '复盘记录' },
  { key: 'experiences', label: '经验总结' },
  { key: 'accounts', label: '账户与配置' },
]

function renderTabPane(key: TabKey) {
  switch (key) {
    case 'workbench':
      return <WorkbenchPane />
    case 'selections':
      return <AgentSelectionsPanel />
    case 'plans':
      return <PlanPanel />
    case 'records':
      return <AgentTradeRecords />
    case 'review':
      return <ReviewPanel />
    case 'experiences':
      return (
        <div className="space-y-3">
          <ExperiencePanel />
          <AgentMemoryPanel />
        </div>
      )
    case 'accounts':
      return (
        <div className="space-y-3">
          <PaperTradeAccountsAdmin />
          <AgentConfigPanel />
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
  const [threadId, setThreadId] = useState<string | undefined>(undefined)
  const lastThreadIdRef = useRef<string | undefined>(undefined)
  const todos = useAssistantStore((state) => state.todos)
  const { sessions, isLoading, deleteSessionById, refresh } = useAssistantSessions({
    agentType: 'trading',
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
              agentType="trading"
              threadId={threadId}
              onThreadIdChange={changeThread}
            >
              <AssistantThread />
            </AssistantRuntimeProvider>
          </AssistantErrorBoundary>
        </div>
      </div>
      <div className="hidden w-[320px] shrink-0 space-y-3 overflow-y-auto lg:block">
        <PlanPanel />
        <ReviewPanel />
      </div>
    </div>
  )
}

export function TradingAgent() {
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
    <div className="flex h-[calc(100dvh-5.75rem)] min-h-[480px] flex-col gap-3 md:h-[calc(100dvh-6.5rem)]">
      <AgentStatusStrip onOpenAccounts={() => changeTab('accounts')} />
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
  )
}
