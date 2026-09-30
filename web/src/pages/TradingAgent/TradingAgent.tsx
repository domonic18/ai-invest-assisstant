/**
 * Agent 详情页（仅 admin，路由 /trading-agent/:agentKey）：单 Agent 闭环统一入口。
 *
 * 结构 = 介绍卡（含「对话」入口：统一打开右侧全局侧边栏与该 Agent 会话）+
 * 运行状态条 + Tabs：Agent 自选（选股清单 + 人工移出）、持仓与交易（agent
 * 账户资金/持仓/委托/成交）、交易计划、执行动态（盘中逐 tick 观测留痕）、
 * 复盘记录（日/周/月）、经验总结（记忆库唯一管理面：复盘沉淀 + 手动沉淀，
 * 可编辑/删除/停用/启用）、配置（基本配置 + 会话人设 + 作业技能 + 模拟盘
 * 账户，D30 四区）。tab 态进 URL query；与 Agent 的对话交互一律走侧边栏。
 */
import { MessageOutlined } from '@ant-design/icons'
import { Button, Spin, Tabs, Tag, Typography } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PAGE_EVENT_TYPES } from '@ai-invest/shared'
import type { TradingAgentProfile } from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useTradingAgentConfig, useTradingAgentLlmOptions, useTradingAgentStatus } from '@/hooks/useTradingAgent'
import { useAssistantStore } from '@/stores/assistant'

import { AgentKeyContext } from './agentKeyContext'

import { AgentAccountPanel } from './AgentAccountPanel'
import { AgentConfigPanel } from './AgentConfigPanel'
import { AgentPersonaPanel } from './AgentPersonaPanel'
import { AgentSkillPanel } from './AgentSkillPanel'
import { AgentMemoryPanel } from './AgentMemoryPanel'
import { AgentSelectionsPanel } from './AgentSelectionsPanel'
import { AgentStatusStrip } from './AgentStatusStrip'
import { AgentTradeRecords } from './AgentTradeRecords'
import { ExecutionTab } from './ExecutionTab'
import { PlanPanel } from './PlanPanel'
import { ReviewPanel } from './ReviewPanel'

const TAB_KEYS = [
  'selections',
  'records',
  'plans',
  'execution',
  'review',
  'experiences',
  'config',
] as const
type TabKey = (typeof TAB_KEYS)[number]

const TAB_ITEMS = [
  { key: 'selections', label: 'Agent 自选' },
  { key: 'records', label: '持仓与交易' },
  { key: 'plans', label: '交易计划' },
  { key: 'execution', label: '执行动态' },
  { key: 'review', label: '复盘记录' },
  { key: 'experiences', label: '经验总结' },
  { key: 'config', label: '配置' },
]

function renderTabPane(key: TabKey) {
  switch (key) {
    case 'selections':
      return <AgentSelectionsPanel />
    case 'records':
      return <AgentTradeRecords />
    case 'plans':
      return <PlanPanel />
    case 'execution':
      return <ExecutionTab />
    case 'review':
      return <ReviewPanel />
    case 'experiences':
      return <AgentMemoryPanel />
    case 'config':
      return (
        <div className="space-y-3">
          <AgentConfigPanel />
          <AgentPersonaPanel />
          <AgentSkillPanel />
          <AgentAccountPanel />
        </div>
      )
  }
}

/** Agent 介绍卡：accent_color 点缀 + 方法论/模型（注册行 + 能力视图）+ 对话入口。 */
function AgentIntroCard({ profile }: { profile: TradingAgentProfile }) {
  const { data: llmOptions } = useTradingAgentLlmOptions()
  const { data: capability } = useTradingAgentStatus(profile.agentKey)
  const setChatAgent = useAssistantStore((state) => state.setChatAgent)
  const openPanel = useAssistantStore((state) => state.openPanel)
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
      <Button
        type="primary"
        size="small"
        icon={<MessageOutlined />}
        className="ml-auto"
        onClick={() => {
          setChatAgent(profile.agentKey)
          openPanel()
        }}
      >
        对话
      </Button>
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

  const rawTab = searchParams.get('tab') ?? 'selections'
  const activeTab: TabKey = (TAB_KEYS as readonly string[]).includes(rawTab)
    ? (rawTab as TabKey)
    : 'selections'
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
