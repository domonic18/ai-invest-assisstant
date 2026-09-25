import { Alert, Button, Card, Form, Select, message } from 'antd'
import { useEffect } from 'react'
import type { LlmPurpose } from '@ai-invest/shared'

import { useKbSettings, useUpdateKbSettings } from '@/hooks/useAdminKb'
import { useLLMConfigs } from '@/hooks/useModelConfig'
import type { ApiKbSettingsResponse, LLMConfig } from '@ai-invest/shared'

interface KbBindingFormValues {
  embeddingConfigId: number | null
  cleanModelId: number | null
  extractModelId: number | null
  visionModelId: number | null
}

const ROLE_FIELDS: {
  name: keyof KbBindingFormValues
  label: string
  purpose: LlmPurpose
  extra: string
}[] = [
  {
    name: 'embeddingConfigId',
    label: '嵌入模型',
    purpose: 'embedding',
    extra: '切片向量化（知识库检索召回），须为 embedding 用途条目',
  },
  {
    name: 'cleanModelId',
    label: '清洗模型',
    purpose: 'chat',
    extra: '转写文稿口语清洗（热词纠错/标点/分段），须为 chat 用途条目',
  },
  {
    name: 'extractModelId',
    label: '抽取模型',
    purpose: 'chat',
    extra: '知识卡片抽取与大纲生成，须为 chat 用途条目',
  },
  {
    name: 'visionModelId',
    label: '视觉模型',
    purpose: 'vision',
    extra: '插图/图表理解（图片转文字），须为 vision 用途条目',
  },
]

function toFormValues(settings: ApiKbSettingsResponse): KbBindingFormValues {
  return {
    embeddingConfigId: settings.embeddingConfigId,
    cleanModelId: settings.cleanModelId,
    extractModelId: settings.extractModelId,
    visionModelId: settings.visionModelId,
  }
}

function RoleSlotSelect({
  config,
  purpose,
  value,
  onChange,
}: {
  config: LLMConfig[]
  purpose: LlmPurpose
  value: number | null | undefined
  onChange: (id: number | null) => void
}) {
  const options = config
    .filter((c) => c.purpose === purpose && c.isActive)
    .map((c) => ({ value: c.id, label: `${c.name}（${c.modelName}）` }))
  return (
    <Select
      value={value ?? undefined}
      onChange={(id) => onChange(id ?? null)}
      options={options}
      allowClear
      placeholder="未配置"
      style={{ width: '100%' }}
      notFoundContent={`暂无「${purpose}」用途的启用条目，请先在「模型条目」中添加`}
    />
  )
}

export function KbBindingTab() {
  const [form] = Form.useForm<KbBindingFormValues>()
  const { data: settings, isLoading } = useKbSettings()
  const { data: configs } = useLLMConfigs()
  const updateMutation = useUpdateKbSettings()

  useEffect(() => {
    if (settings) form.setFieldsValue(toFormValues(settings))
  }, [settings, form])

  const handleSave = async (values: KbBindingFormValues) => {
    try {
      await updateMutation.mutateAsync(values)
      message.success('知识库模型绑定已保存')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <Card title="知识库模型绑定" variant="borderless">
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
          message="四个角色均指向「模型条目」，按用途过滤；条目停用或改用途后管线任务会显式报错而非静默走错模型"
        />
        {ROLE_FIELDS.map((role) => (
          <Form.Item key={role.name} label={role.label} name={role.name} extra={role.extra}>
            <RoleSlotSelect
              config={configs ?? []}
              purpose={role.purpose}
              value={form.getFieldValue(role.name)}
              onChange={(id) => form.setFieldValue(role.name, id)}
            />
          </Form.Item>
        ))}
        <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
          保存绑定
        </Button>
      </Form>
    </Card>
  )
}
