/**
 * Agent 配置卡片（批次 5）：对话模型 + 风控阈值 + 盘中自主执行总闸。
 *
 * 模拟管理页「账户与配置」tab 内使用；数据源 admin GET/PUT /trading-agent/config。
 */
import { Button, Card, Form, InputNumber, Select, Spin, Switch, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect } from 'react'

import {
  useTradingAgentConfig,
  useTradingAgentLlmOptions,
  useUpdateTradingAgentConfig,
} from '@/hooks/useTradingAgent'

interface ConfigFormValues {
  llmConfigId?: number | null
  riskMaxPositionPct: number
  riskMaxTotalPct: number
  riskMaxDailyOrders: number
  autoExecEnabled: boolean
}

export function AgentConfigPanel() {
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
          <div className="grid gap-x-6 md:grid-cols-2 xl:grid-cols-4">
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
