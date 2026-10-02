import { SoundOutlined } from '@ant-design/icons'
import { Alert, Button, Form, Input, InputNumber, Modal, Select, Space, Switch, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { ASR_PROVIDER_PRESETS } from '@ai-invest/shared'
import type { ApiAsrConfig, ApiAsrConfigTestResult, AsrProtocol } from '@ai-invest/shared'

import { useTestAsrConfig } from '@/hooks/useModelConfig'

interface AsrConfigModalProps {
  open: boolean
  config: ApiAsrConfig | null
  loading: boolean
  onCancel: () => void
  onSubmit: (values: {
    provider?: string
    protocol?: AsrProtocol
    baseUrl?: string
    model?: string
    apiKey?: string
    maxAudioSeconds?: number
    hotwords?: string[]
    enabled?: boolean
  }) => void
}

interface AsrFormValues {
  provider: string
  protocol: AsrProtocol
  baseUrl: string
  model: string
  apiKey?: string
  maxAudioSeconds: number
  hotwordsText?: string
  enabled: boolean
}

const PROVIDER_OPTIONS = [
  ...Object.entries(ASR_PROVIDER_PRESETS).map(([value, preset]) => ({
    value,
    label: preset.label,
  })),
  { value: 'custom', label: '自定义' },
]

const PROTOCOL_OPTIONS: { value: AsrProtocol; label: string }[] = [
  { value: 'minimax', label: 'MiniMax 专有' },
  { value: 'openai', label: 'OpenAI 兼容' },
]

// 存量 provider 不在预设中（如历史自定义值）按「自定义」展示，字段保留现值
function knownProvider(provider: string | undefined) {
  return provider !== undefined && provider in ASR_PROVIDER_PRESETS
}

export function AsrConfigModal({
  open,
  config,
  loading,
  onCancel,
  onSubmit,
}: AsrConfigModalProps) {
  const [form] = Form.useForm<AsrFormValues>()
  const [testResult, setTestResult] = useState<ApiAsrConfigTestResult | null>(null)
  const testMutation = useTestAsrConfig()
  const provider = Form.useWatch('provider', form)
  // 协议由供应商预设派生：预设供应商锁定展示，自定义可手切
  const protocolLocked = knownProvider(provider)

  useEffect(() => {
    if (!open) return
    setTestResult(null)
    form.resetFields()
    if (config) {
      form.setFieldsValue({
        provider: knownProvider(config.provider) ? config.provider : 'custom',
        protocol: config.protocol ?? 'minimax',
        baseUrl: config.baseUrl,
        model: config.model,
        maxAudioSeconds: config.maxAudioSeconds,
        hotwordsText: config.hotwords.join('\n'),
        enabled: config.enabled,
      })
    }
  }, [open, config, form])

  const handleProviderChange = (value: string) => {
    const preset = ASR_PROVIDER_PRESETS[value]
    if (!preset) return // 自定义：保留手填地址/模型
    form.setFieldsValue({
      baseUrl: preset.baseUrl,
      model: preset.model,
      protocol: preset.protocol,
    })
  }

  const handleTest = async () => {
    setTestResult(null)
    try {
      setTestResult(await testMutation.mutateAsync())
    } catch (err) {
      setTestResult({
        ok: false,
        latencyMs: 0,
        text: null,
        error: err instanceof Error ? err.message : '测试请求失败',
      })
    }
  }

  const protocolOptions = protocolLocked
    ? PROTOCOL_OPTIONS.filter((o) => o.value === form.getFieldValue('protocol'))
    : PROTOCOL_OPTIONS

  return (
    <Modal
      title="ASR 转写配置"
      open={open}
      onCancel={onCancel}
      destroyOnHidden
      width={640}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="test"
          icon={<SoundOutlined />}
          loading={testMutation.isPending}
          onClick={handleTest}
        >
          测试连接
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={() => form.submit()}>
          保存
        </Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) =>
          onSubmit({
            provider: values.provider,
            protocol: values.protocol,
            baseUrl: values.baseUrl,
            model: values.model,
            apiKey: values.apiKey || undefined,
            maxAudioSeconds: values.maxAudioSeconds,
            hotwords: (values.hotwordsText ?? '')
              .split('\n')
              .map((w) => w.trim())
              .filter(Boolean),
            enabled: values.enabled,
          })
        }
      >
        <Space align="baseline" className="w-full">
          <Form.Item
            name="provider"
            label="供应商"
            rules={[{ required: true, message: '请选择供应商' }]}
            extra="预设供应商自动填充地址/模型与协议；本地部署选「自定义」"
          >
            <Select
              options={PROVIDER_OPTIONS}
              onChange={handleProviderChange}
              style={{ width: 160 }}
            />
          </Form.Item>
          <Form.Item
            name="protocol"
            label="调用协议"
            rules={[{ required: true, message: '请选择协议' }]}
            extra={
              protocolLocked
                ? '由供应商决定'
                : '决定端点形状：OpenAI 兼容走 /v1/audio/transcriptions，MiniMax 专有走 /v1/speech_to_text'
            }
          >
            <Select options={protocolOptions} disabled={protocolLocked} style={{ width: 160 }} />
          </Form.Item>
        </Space>
        <Space align="baseline" className="w-full">
          <Form.Item
            name="baseUrl"
            label="Base URL"
            rules={[{ required: true, message: '请输入服务 Base URL' }]}
            extra="填 API 根地址（OpenAI 兼容须含 /v1）；粘贴完整端点会自动归一"
          >
            <Input placeholder="https://api.groq.com/openai/v1" style={{ width: 320 }} />
          </Form.Item>
          <Form.Item
            name="model"
            label="模型"
            rules={[{ required: true, message: '请输入模型名' }]}
          >
            <Input placeholder="如 whisper-large-v3" style={{ width: 160 }} />
          </Form.Item>
        </Space>
        <Form.Item
          name="apiKey"
          label="API Key"
          extra={
            config?.apiKeyConfigured
              ? `已配置（${config.apiKeyMasked ?? '****'}），留空保留原值`
              : '首次使用请填写；本地无鉴权服务可留空'
          }
        >
          <Input.Password placeholder={config?.apiKeyConfigured ? '留空保留原值' : 'sk-...'} autoComplete="new-password" />
        </Form.Item>
        <Form.Item
          name="maxAudioSeconds"
          label="单条音频时长上限（秒）"
          rules={[{ required: true, message: '请输入时长上限' }]}
          extra="超上限的音频直接降级为未转写，不阻塞内容入库"
        >
          <InputNumber min={30} max={3600} style={{ width: 160 }} />
        </Form.Item>
        <Form.Item
          name="hotwordsText"
          label="热词表（每行一个）"
          extra="转写接口无热词参数；热词注入情绪判断 prompt 纠偏口播术语"
        >
          <Input.TextArea rows={3} placeholder={'美联储\n北向资金\n集合竞价'} />
        </Form.Item>
        <Form.Item name="enabled" label="启用转写" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Alert
          type="info"
          showIcon
          message="关闭后采集侧直接降级为未转写（判断仅基于标题/文案），历史文稿不受影响"
        />
        {testResult && (
          <Alert
            className="mt-3"
            type={testResult.ok ? 'success' : 'error'}
            showIcon
            message={
              testResult.ok
                ? `连接正常（${testResult.latencyMs}ms）`
                : `连接失败（${testResult.latencyMs}ms）`
            }
            description={
              testResult.ok
                ? testResult.text
                  ? `样例转写：${testResult.text}`
                  : '样例音频为无人声正弦波，转写为空属正常'
                : testResult.error ?? '未知错误'
            }
          />
        )}
        <Typography.Paragraph type="secondary" className="!mb-0 mt-3">
          保存后即刻生效：采集任务在转写时读取此配置，无需重启服务。
        </Typography.Paragraph>
      </Form>
    </Modal>
  )
}
