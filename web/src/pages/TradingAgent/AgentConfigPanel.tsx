/**
 * Agent 基本配置卡片（D30 精简）：名称 + 启用状态 + 计划/复盘频率 +
 * 对话模型 + 风控阈值 + 盘中自主执行总闸。人设标语/策略文案不在表单编辑
 * （展示空值收敛），会话人设与作业技能分属配置页独立区块。
 *
 * Agent 详情页「配置」tab 首区块；数据源 admin GET/PUT /trading-agent/config
 *（D28 起任意状态可编辑；停用 = 雷达隐藏且不参与调度）。
 */
import { Button, Card, Form, Input, InputNumber, Select, Spin, Switch, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect } from 'react'

import type { AgentCadence } from '@ai-invest/shared'

import { useAgentKey } from './agentKeyContext'
import {
  useTradingAgentConfig,
  useTradingAgentLlmOptions,
  useUpdateTradingAgentConfig,
} from '@/hooks/useTradingAgent'

const CADENCE_OPTIONS: { value: AgentCadence; label: string }[] = [
  { value: 'daily', label: '每个交易日' },
  { value: 'weekly', label: '每周最后一个交易日' },
  { value: 'monthly', label: '每月最后一个交易日' },
]

interface ConfigFormValues {
  name: string
  statusEnabled: boolean
  planCadence: AgentCadence
  reviewCadence: AgentCadence
  llmConfigId?: number | null
  riskMaxPositionPct: number
  riskMaxTotalPct: number
  riskMaxDailyOrders: number
  autoExecEnabled: boolean
}

export function AgentConfigPanel() {
  const [form] = Form.useForm<ConfigFormValues>()
  const agentKey = useAgentKey()
  const { data: config, isLoading } = useTradingAgentConfig(agentKey)
  const { data: llmOptions, isLoading: llmLoading } = useTradingAgentLlmOptions()
  const update = useUpdateTradingAgentConfig(agentKey)

  useEffect(() => {
    if (config) {
      form.setFieldsValue({
        name: config.name,
        statusEnabled: config.status === 'active',
        planCadence: config.planCadence,
        reviewCadence: config.reviewCadence,
        llmConfigId: config.llmConfigId ?? null,
        riskMaxPositionPct: config.riskMaxPositionPct,
        riskMaxTotalPct: config.riskMaxTotalPct,
        riskMaxDailyOrders: config.riskMaxDailyOrders,
        autoExecEnabled: config.autoExecEnabled,
      })
    }
  }, [config, form])

  return (
    <Card size="small" title="基本配置">
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
              name: values.name,
              status: values.statusEnabled ? 'active' : 'disabled',
              planCadence: values.planCadence,
              reviewCadence: values.reviewCadence,
              llmConfigId: values.llmConfigId ?? null,
              riskMaxPositionPct: values.riskMaxPositionPct,
              riskMaxTotalPct: values.riskMaxTotalPct,
              riskMaxDailyOrders: values.riskMaxDailyOrders,
              autoExecEnabled: values.autoExecEnabled,
            })
          }
        >
          <Typography.Text type="secondary" className="text-xs">
            状态与频率（停用后总览雷达不再显示，且不参与计划/复盘调度）
          </Typography.Text>
          <div className="mt-2 grid gap-x-6 md:grid-cols-2 xl:grid-cols-4">
            <Form.Item name="name" label="名称" rules={[{ required: true, message: '必填' }]}>
              <Input placeholder="如：短线猎手" />
            </Form.Item>
            <Form.Item name="statusEnabled" label="启用" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
            <Form.Item name="planCadence" label="计划生成频率" extra="低于每日的频率仅在周期末生成">
              <Select options={CADENCE_OPTIONS} />
            </Form.Item>
            <Form.Item name="reviewCadence" label="复盘生成频率" extra="低于每日的频率仅在周期末生成">
              <Select options={CADENCE_OPTIONS} />
            </Form.Item>
          </div>

          <Typography.Text type="secondary" className="text-xs">
            模型与风控
          </Typography.Text>
          <div className="mt-2 grid gap-x-6 md:grid-cols-2 xl:grid-cols-4">
            <Form.Item
              name="llmConfigId"
              label="对话模型"
              extra="留空使用平台默认 chat 模型；仅列出启用中的 chat 用途配置"
              className="xl:col-span-2"
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
          </div>
          <div className="flex items-center justify-end gap-3">
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
