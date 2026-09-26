/**
 * 新建交易 Agent 弹窗（D29）：注册表 CRUD 前端面。
 * 创建即 active——出现在总览雷达并参与调度；技能走 trading-default 共享兜底，
 * 提示需绑定模拟盘账户后才会实际下单。
 */
import { Button, ColorPicker, Form, Input, Modal, Select } from 'antd'
import { useEffect } from 'react'

import type { AgentCadence } from '@ai-invest/shared'

import { useCreateTradingAgent, useTradingAgentPromptTemplates } from '@/hooks/useTradingAgent'

const AGENT_KEY_PATTERN = /^[a-z0-9][a-z0-9-]{1,31}$/

const CADENCE_OPTIONS: { value: AgentCadence; label: string }[] = [
  { value: 'daily', label: '每日（每交易日）' },
  { value: 'weekly', label: '每周（周期末交易日）' },
  { value: 'monthly', label: '每月（月末交易日）' },
]

interface AgentCreateFormValues {
  agentKey: string
  name: string
  promptId: string
  accentColor?: { toHexString: () => string } | string
  planCadence?: AgentCadence
  reviewCadence?: AgentCadence
}

export function AgentCreateModal({ open, onCancel }: { open: boolean; onCancel: () => void }) {
  const [form] = Form.useForm<AgentCreateFormValues>()
  const templates = useTradingAgentPromptTemplates()
  const create = useCreateTradingAgent()

  useEffect(() => {
    if (open) {
      form.resetFields()
      form.setFieldsValue({ planCadence: 'daily', reviewCadence: 'daily', accentColor: '#38bdf8' })
    }
  }, [open, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    const accent = values.accentColor
    create.mutate(
      {
        agentKey: values.agentKey,
        name: values.name,
        promptId: values.promptId,
        accentColor: typeof accent === 'string' ? accent : (accent?.toHexString() ?? null),
        planCadence: values.planCadence ?? null,
        reviewCadence: values.reviewCadence ?? null,
      },
      { onSuccess: onCancel },
    )
  }

  return (
    <Modal
      title="新建 Agent"
      open={open}
      onOk={() => void handleOk()}
      onCancel={onCancel}
      confirmLoading={create.isPending}
      destroyOnClose
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button key="ok" type="primary" loading={create.isPending} onClick={() => void handleOk()}>
          创建并启用
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Form.Item
          label="Agent Key"
          name="agentKey"
          rules={[
            { required: true, message: '请输入 agent key' },
            {
              pattern: AGENT_KEY_PATTERN,
              message: '2-32 位小写字母/数字/连字符，字母或数字开头',
            },
          ]}
          extra="URL 与调度的唯一标识，创建后不可修改"
        >
          <Input placeholder="如：swing-line" />
        </Form.Item>

        <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
          <Input placeholder="如：波段舵手" maxLength={64} />
        </Form.Item>

        <Form.Item
          label="会话人设模板"
          name="promptId"
          rules={[{ required: true, message: '请选择人设模板' }]}
          extra="决定对话身份与硬纪律骨架；创建后可在配置页浏览与换绑"
        >
          <Select
            loading={templates.isLoading}
            options={(templates.data ?? []).map((t) => ({ value: t.promptId, label: t.label }))}
            placeholder="选择人设模板"
          />
        </Form.Item>

        <Form.Item label="计划频率" name="planCadence" extra="停用/未绑定账户时不生成">
          <Select options={CADENCE_OPTIONS} />
        </Form.Item>

        <Form.Item label="复盘频率" name="reviewCadence">
          <Select options={CADENCE_OPTIONS} />
        </Form.Item>

        <Form.Item label="节点主色" name="accentColor">
          <ColorPicker showText format="hex" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
