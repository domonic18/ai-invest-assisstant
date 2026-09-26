/**
 * 交易 Agent 页（批次 5，仅 admin）：专属对话区 + 配置区。
 *
 * 对话区复用 components/assistant 会话组件（agentType='trading'，线程态由本页
 * 持有，新线程创建携带 agent_type 由后端分流至交易 Agent 运行时）；配置区
 * 绑定对话模型与风控阈值、盘中自主执行总闸。
 */
import { EditOutlined } from '@ant-design/icons'
import { Button, Card, Form, InputNumber, Select, Spin, Switch, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { PAGE_EVENT_TYPES } from '@ai-invest/shared'

import { useAssistantSessions } from '@/components/assistant/hooks/useAssistantSessions'
import { AssistantErrorBoundary } from '@/components/assistant/AssistantErrorBoundary'
import { AssistantRuntimeProvider } from '@/components/assistant/AssistantRuntimeProvider'
import { AssistantSidebar } from '@/components/assistant/AssistantSidebar'
import { AssistantThread } from '@/components/assistant/AssistantThread'
import { TodoListBar } from '@/components/assistant/ui/TodoListBar'
import { queryKeys } from '@/hooks/queryKeys'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import {
  useTradingAgentConfig,
  useTradingAgentLlmOptions,
  useUpdateTradingAgentConfig,
} from '@/hooks/useTradingAgent'
import { useAssistantStore } from '@/stores/assistant'

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

interface ConfigFormValues {
  llmConfigId?: number | null
  riskMaxPositionPct: number
  riskMaxTotalPct: number
  riskMaxDailyOrders: number
  autoExecEnabled: boolean
}

function AgentConfigPanel() {
  const [form] = Form.useForm<ConfigFormValues>()
  const { data: config, isLoading } = useTradingAgentConfig()
  const { data: llmOptions, isLoading: llmLoading } = useTradingAgentLlmOptions()
  const update = useUpdateTradingAgentConfig()

  useEffect(() => {
    if (config) {
      form.setFieldsValue({
        llmConfigId: config.llmConfigId ?? null,
        riskMaxPositionPct: config.riskMaxPositionPct,
        riskMaxTotalPct: config.riskMaxTotalPct,
        riskMaxDailyOrders: config.riskMaxDailyOrders,
        autoExecEnabled: config.autoExecEnabled,
      })
    }
  }, [config, form])

  return (
    <Card size="small" title="Agent 配置">
      {isLoading || !config ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : (
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) =>
            update.mutate({
              llmConfigId: values.llmConfigId ?? null,
              riskMaxPositionPct: values.riskMaxPositionPct,
              riskMaxTotalPct: values.riskMaxTotalPct,
              riskMaxDailyOrders: values.riskMaxDailyOrders,
              autoExecEnabled: values.autoExecEnabled,
            })
          }
        >
          <Form.Item
            name="llmConfigId"
            label="对话模型"
            extra="留空使用平台默认 chat 模型；仅列出启用中的 chat 用途配置"
          >
            <Select
              allowClear
              loading={llmLoading}
              placeholder="平台默认"
              options={llmOptions ?? []}
            />
          </Form.Item>
          <Form.Item
            name="riskMaxPositionPct"
            label="单票市值上限（占总资产）"
            rules={[{ required: true, message: '必填' }]}
          >
            <InputNumber className="w-full" min={0} max={100} step={1} addonAfter="%" />
          </Form.Item>
          <Form.Item
            name="riskMaxTotalPct"
            label="总持仓上限（占总资产）"
            rules={[{ required: true, message: '必填' }]}
          >
            <InputNumber className="w-full" min={0} max={100} step={1} addonAfter="%" />
          </Form.Item>
          <Form.Item
            name="riskMaxDailyOrders"
            label="单日委托笔数上限"
            rules={[{ required: true, message: '必填' }]}
          >
            <InputNumber className="w-full" min={1} step={1} precision={0} />
          </Form.Item>
          <Form.Item
            name="autoExecEnabled"
            label="盘中自主执行"
            valuePropName="checked"
            extra="关闭后盘中不自动执行交易计划（对话内交易不受影响）"
          >
            <Switch />
          </Form.Item>
          <div className="flex items-center justify-between">
            <Typography.Text type="secondary" className="text-xs">
              {config.updatedAt
                ? `更新于 ${dayjs(config.updatedAt).format('YYYY-MM-DD HH:mm')}`
                : null}
            </Typography.Text>
            <Button type="primary" htmlType="submit" loading={update.isPending}>
              保存
            </Button>
          </div>
        </Form>
      )}
    </Card>
  )
}

export function TradingAgent() {
  const [threadId, setThreadId] = useState<string | undefined>(undefined)
  const lastThreadIdRef = useRef<string | undefined>(undefined)
  const todos = useAssistantStore((state) => state.todos)
  const { sessions, isLoading, deleteSessionById, refresh } = useAssistantSessions({
    agentType: 'trading',
  })
  const queryClient = useQueryClient()

  // Agent 委托成功事件：刷新模拟盘数据（执行动态/持仓），事件即消费
  usePageAssistantResult(PAGE_EVENT_TYPES.paperTrading, () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
    return true
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
    <div className="flex h-[calc(100dvh-5.75rem)] min-h-[480px] gap-3 md:h-[calc(100dvh-6.5rem)]">
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
      <div className="hidden w-[320px] shrink-0 overflow-y-auto lg:block">
        <AgentConfigPanel />
      </div>
    </div>
  )
}
