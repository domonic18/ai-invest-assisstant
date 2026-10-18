import { Alert, Button, Card, Form, Select, Typography, message } from 'antd'
import { useEffect } from 'react'
import type { AiTaskKey } from '@ai-invest/shared'

import { useLLMConfigs, useReplaceTaskBindings, useTaskBindings } from '@/hooks/useModelConfig'
import type { ApiTaskBindingSlot, LLMConfig } from '@ai-invest/shared'

type TaskBindingFormValues = Record<AiTaskKey, number | null>

function toFormValues(slots: ApiTaskBindingSlot[]): TaskBindingFormValues {
  return Object.fromEntries(slots.map((slot) => [slot.taskKey, slot.configId])) as TaskBindingFormValues
}

function TaskSlotSelect({
  config,
  value,
  onChange,
}: {
  config: LLMConfig[]
  value: number | null | undefined
  onChange: (id: number | null) => void
}) {
  const options = config
    .filter((c) => c.purpose === 'chat' && c.isActive)
    .map((c) => ({ value: c.id, label: `${c.name}（${c.modelName}）` }))
  return (
    <Select
      value={value ?? undefined}
      onChange={(id) => onChange(id ?? null)}
      options={options}
      allowClear
      placeholder="跟随系统默认"
      style={{ width: '100%' }}
      notFoundContent="暂无「chat」用途的启用条目，请先在「模型条目」中添加"
    />
  )
}

export function TaskBindingTab() {
  const [form] = Form.useForm<TaskBindingFormValues>()
  const { data: slots, isLoading } = useTaskBindings()
  const { data: configs } = useLLMConfigs()
  const replaceMutation = useReplaceTaskBindings()

  useEffect(() => {
    if (slots) form.setFieldsValue(toFormValues(slots))
  }, [slots, form])

  const handleSave = async (values: TaskBindingFormValues) => {
    try {
      await replaceMutation.mutateAsync({
        bindings: Object.entries(values).map(([taskKey, configId]) => ({
          taskKey: taskKey as AiTaskKey,
          configId: configId ?? null,
        })),
      })
      message.success('任务模型绑定已保存')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <Card title="任务模型" variant="borderless">
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        disabled={isLoading}
        style={{ maxWidth: 640 }}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="定时 AI 任务默认共用系统默认模型（主模型+备用主备链）；此处可为单个任务绑定独立条目——轻任务绑廉价模型省 token，重任务绑强模型。绑定条目失效（停用/删除）后任务自动降级回系统默认；换绑后当日已生成的分析结果不会自动重算"
        />
        {(slots ?? []).map((slot: ApiTaskBindingSlot) => (
          <Form.Item
            key={slot.taskKey}
            name={slot.taskKey}
            label={<Typography.Text strong>{slot.label}</Typography.Text>}
            extra={slot.description}
          >
            <TaskSlotSelect
              config={configs ?? []}
              value={form.getFieldValue(slot.taskKey)}
              onChange={(id) => form.setFieldValue(slot.taskKey, id)}
            />
          </Form.Item>
        ))}
        <Button type="primary" htmlType="submit" loading={replaceMutation.isPending}>
          保存绑定
        </Button>
      </Form>
    </Card>
  )
}
