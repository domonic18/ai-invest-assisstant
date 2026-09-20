import { Alert, Button, Card, Form, InputNumber, Select, Space, message } from 'antd'
import { useEffect } from 'react'

import type { ApiKbSettingsResponse, LlmPurpose } from '@ai-invest/shared'

import { useKbSettings, useUpdateKbSettings } from '@/hooks/useAdminKb'
import { useLLMConfigs } from '@/hooks/useLLMConfigs'
import type { LLMConfig } from '@ai-invest/shared'

interface KbSettingsFormValues {
  embeddingConfigId: number | null
  cleanModelId: number | null
  extractModelId: number | null
  visionModelId: number | null
  topK: number
  segmentMaxSeconds: number
  asrConcurrency: number
  asrPerHour: number | null
  hotwords: string[]
}

const ROLE_FIELDS: {
  name: keyof KbSettingsFormValues
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

function toFormValues(settings: ApiKbSettingsResponse): KbSettingsFormValues {
  return {
    embeddingConfigId: settings.embeddingConfigId,
    cleanModelId: settings.cleanModelId,
    extractModelId: settings.extractModelId,
    visionModelId: settings.visionModelId,
    topK: settings.topK,
    segmentMaxSeconds: settings.segmentMaxSeconds,
    asrConcurrency: settings.asrConcurrency,
    asrPerHour:
      typeof settings.unitPrices?.asrPerHour === 'number'
        ? settings.unitPrices.asrPerHour
        : null,
    hotwords: settings.hotwords,
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
      notFoundContent={`暂无「${purpose}」用途的启用条目，请先在「模型配置」中添加`}
    />
  )
}

export function SettingsTab() {
  const [form] = Form.useForm<KbSettingsFormValues>()
  const { data: settings, isLoading } = useKbSettings()
  const { data: configs } = useLLMConfigs()
  const updateMutation = useUpdateKbSettings()

  useEffect(() => {
    if (settings) form.setFieldsValue(toFormValues(settings))
  }, [settings, form])

  const handleSave = async (values: KbSettingsFormValues) => {
    const { asrPerHour, ...rest } = values
    try {
      await updateMutation.mutateAsync({
        ...rest,
        unitPrices: {
          ...(settings?.unitPrices ?? {}),
          ...(asrPerHour != null ? { asrPerHour } : {}),
        },
      })
      message.success('知识库设置已保存')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSave}
      disabled={isLoading}
      style={{ maxWidth: 640 }}
    >
      <Card type="inner" title="模型角色" style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="四个角色均指向「模型配置」中的条目，按用途过滤；条目停用或改用途后管线任务会显式报错而非静默走错模型"
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
      </Card>

      <Card type="inner" title="域参数" style={{ marginBottom: 16 }}>
        <Space wrap size="large">
          <Form.Item
            label="检索 top K"
            name="topK"
            rules={[{ required: true, message: '请输入' }]}
            extra="检索召回的知识片段数量"
          >
            <InputNumber min={1} max={50} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item
            label="音频分段上限（秒）"
            name="segmentMaxSeconds"
            rules={[{ required: true, message: '请输入' }]}
            extra="ASR 单请求分段时长上限"
          >
            <InputNumber min={5} max={120} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item
            label="ASR 并发数"
            name="asrConcurrency"
            rules={[{ required: true, message: '请输入' }]}
            extra="转写分片并发请求上限"
          >
            <InputNumber min={1} max={8} style={{ width: 120 }} />
          </Form.Item>
        </Space>
        <Form.Item
          label="热词"
          name="hotwords"
          extra="转写与清洗时提升专有名词识别（回车添加）"
        >
          <Select mode="tags" open={false} placeholder="输入后回车添加" style={{ width: '100%' }} />
        </Form.Item>
      </Card>

      <Card type="inner" title="计价" style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="转写单价用于「预估费用」与实际用量核算；未配置时费用预估会显式拒绝"
        />
        <Form.Item
          label="转写单价（元/小时）"
          name="asrPerHour"
          extra="ASR 按音频时长计费的单价，来自渠道刊例（如 asr-1.0）"
          rules={[{ required: true, message: '请输入转写单价' }]}
        >
          <InputNumber min={0.01} step={0.1} style={{ width: 160 }} />
        </Form.Item>
      </Card>

      <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
        保存设置
      </Button>
    </Form>
  )
}
