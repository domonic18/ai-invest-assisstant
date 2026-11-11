import { Alert, Button, Card, Form, Select, Typography, message } from 'antd'
import { useEffect } from 'react'
import type { AiTaskKey, LlmPurpose } from '@ai-invest/shared'

import { useLLMConfigs, useReplaceTaskBindings, useTaskBindings } from '@/hooks/useModelConfig'
import type { ApiTaskBindingSlot, LLMConfig } from '@ai-invest/shared'

interface TaskBindingSlotValue {
  configId: number | null
  backupConfigId: number | null
}

type TaskBindingFormValues = Record<string, TaskBindingSlotValue>

function toFormValues(slots: ApiTaskBindingSlot[]): TaskBindingFormValues {
  return Object.fromEntries(
    slots.map((slot) => [
      slot.taskKey,
      { configId: slot.configId, backupConfigId: slot.backupConfigId ?? null },
    ]),
  )
}

function TaskModelSelect({
  config,
  purpose,
  value,
  onChange,
  allowEmpty,
  placeholder,
}: {
  config: LLMConfig[]
  purpose: LlmPurpose
  value: number | null | undefined
  onChange: (id: number | null) => void
  allowEmpty: boolean
  placeholder: string
}) {
  const options = config
    .filter((c) => c.purpose === purpose && c.isActive)
    .map((c) => ({ value: c.id, label: `${c.name}（${c.modelName}）` }))
  return (
    <Select
      value={value ?? undefined}
      onChange={(id) => onChange(id ?? null)}
      onClear={() => onChange(null)}
      options={options}
      allowClear={allowEmpty}
      placeholder={placeholder}
      style={{ width: '100%' }}
      notFoundContent={`暂无「${purpose}」用途的启用条目，请先在「模型条目」中添加`}
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
        bindings: Object.entries(values).map(([taskKey, slotValue]) => ({
          taskKey: taskKey as AiTaskKey,
          // 必填校验已保证主模型非空，这里的 as number 仅收窄表单值类型
          configId: (slotValue?.configId ?? null) as number,
          backupConfigId: slotValue?.backupConfigId ?? null,
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
          message="每槽位绑定主模型（必填）与可选备用；主模型额度耗尽或连接中断冷却期内自动切备用，冷却结束自动恢复；主备皆不可用时任务失败并告警。换绑后当日已生成的分析结果不会自动重算"
        />
        {(slots ?? []).map((slot: ApiTaskBindingSlot) => (
          <div key={slot.taskKey}>
            <Typography.Text strong>{slot.label}</Typography.Text>
            {slot.description && (
              <Typography.Paragraph type="secondary" style={{ marginBottom: 4 }}>
                {slot.description}
              </Typography.Paragraph>
            )}
            <Form.Item
              name={[slot.taskKey, 'configId']}
              label="主模型"
              rules={[{ required: true, message: '请选择主模型' }]}
              style={{ marginBottom: 8 }}
            >
              <TaskModelSelect
                config={configs ?? []}
                purpose={slot.purpose}
                value={form.getFieldValue([slot.taskKey, 'configId'])}
                onChange={(id) => form.setFieldValue([slot.taskKey, 'configId'], id)}
                allowEmpty={false}
                placeholder="请选择主模型"
              />
            </Form.Item>
            <Form.Item
              name={[slot.taskKey, 'backupConfigId']}
              label="备用模型"
              extra={
                slot.backupConfigName
                  ? `当前备用：${slot.backupConfigName}（${slot.backupModelName ?? ''}）`
                  : undefined
              }
            >
              <TaskModelSelect
                config={(configs ?? []).filter(
                  (c) => c.id !== form.getFieldValue([slot.taskKey, 'configId']),
                )}
                purpose={slot.purpose}
                value={form.getFieldValue([slot.taskKey, 'backupConfigId'])}
                onChange={(id) => {
                  if (id === form.getFieldValue([slot.taskKey, 'configId'])) {
                    message.warning('备用模型不能与主模型相同')
                    form.setFieldValue([slot.taskKey, 'backupConfigId'], null)
                    return
                  }
                  form.setFieldValue([slot.taskKey, 'backupConfigId'], id)
                }}
                allowEmpty={true}
                placeholder="可选备用"
              />
            </Form.Item>
          </div>
        ))}
        <Button type="primary" htmlType="submit" loading={replaceMutation.isPending}>
          保存绑定
        </Button>
      </Form>
    </Card>
  )
}
