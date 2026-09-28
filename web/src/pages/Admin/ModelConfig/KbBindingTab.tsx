import { Alert, Button, Card, Form, Select, message } from 'antd'
import { useEffect } from 'react'
import type { LlmPurpose } from '@ai-invest/shared'

import { useKbSettings, useUpdateKbSettings } from '@/hooks/useAdminKb'
import { useLLMConfigs } from '@/hooks/useModelConfig'
import type { ApiKbSettingsResponse, LLMConfig, LLMConfigCapabilities } from '@ai-invest/shared'

interface KbBindingFormValues {
  embeddingConfigId: number | null
  cleanModelId: number | null
  extractModelId: number | null
  visionModelId: number | null
}

// 候选过滤谓词（与后端 settings_service._role_accepts 同规则）
function purposeIs(purpose: LlmPurpose) {
  return (c: LLMConfig) => c.purpose === purpose
}

// 视觉槽按「视觉能力」而非「vision 用途」判定（与后端 _role_accepts 同规则）：
// vision 用途条目，或勾选「视觉能力」的对话条目
function acceptsVision(c: LLMConfig) {
  if (c.purpose === 'vision') return true
  const capabilities = (c.extra?.capabilities ?? {}) as LLMConfigCapabilities
  return c.purpose === 'chat' && capabilities.vision === true
}

const ROLE_FIELDS: {
  name: keyof KbBindingFormValues
  label: string
  accepts: (c: LLMConfig) => boolean
  extra: string
  notFound: string
}[] = [
  {
    name: 'embeddingConfigId',
    label: '嵌入模型',
    accepts: purposeIs('embedding'),
    extra: '切片向量化（知识库检索召回），须为 embedding 用途条目',
    notFound: '暂无「embedding」用途的启用条目，请先在「模型条目」中添加',
  },
  {
    name: 'cleanModelId',
    label: '清洗模型',
    accepts: purposeIs('chat'),
    extra: '转写文稿口语清洗（热词纠错/标点/分段），须为 chat 用途条目',
    notFound: '暂无「chat」用途的启用条目，请先在「模型条目」中添加',
  },
  {
    name: 'extractModelId',
    label: '抽取模型',
    accepts: purposeIs('chat'),
    extra: '知识卡片抽取与大纲生成，须为 chat 用途条目',
    notFound: '暂无「chat」用途的启用条目，请先在「模型条目」中添加',
  },
  {
    name: 'visionModelId',
    label: '视觉模型',
    accepts: acceptsVision,
    extra: '插图/图表理解（图片转文字），vision 用途或勾选「视觉能力」的对话条目均可',
    notFound: '暂无开启视觉能力的启用条目（vision 用途，或对话条目勾选「视觉能力」）',
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
  accepts,
  notFound,
  value,
  onChange,
}: {
  config: LLMConfig[]
  accepts: (c: LLMConfig) => boolean
  notFound: string
  value: number | null | undefined
  onChange: (id: number | null) => void
}) {
  const options = config
    .filter((c) => accepts(c) && c.isActive)
    .map((c) => ({ value: c.id, label: `${c.name}（${c.modelName}）` }))
  return (
    <Select
      value={value ?? undefined}
      onChange={(id) => onChange(id ?? null)}
      options={options}
      allowClear
      placeholder="未配置"
      style={{ width: '100%' }}
      notFoundContent={notFound}
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
          message="四个角色均指向「模型条目」，按用途过滤（视觉模型按「视觉能力」判定：vision 用途或勾选视觉能力的对话条目）；条目停用或不满足要求后管线任务会显式报错而非静默走错模型"
        />
        {ROLE_FIELDS.map((role) => (
          <Form.Item key={role.name} label={role.label} name={role.name} extra={role.extra}>
            <RoleSlotSelect
              config={configs ?? []}
              accepts={role.accepts}
              notFound={role.notFound}
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
