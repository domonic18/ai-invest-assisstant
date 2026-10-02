import { ExperimentOutlined } from '@ant-design/icons'
import { Button, Divider, Form, Input, Modal, Select, Switch } from 'antd'
import { useEffect } from 'react'

import { LLM_PROVIDER_PRESETS } from '@ai-invest/shared'
import type { LLMConfig, LLMConfigFormValues, LLMProtocol, LlmPurpose } from '@ai-invest/shared'

import { chatProtocolForProvider, protocolForPurpose, resolvePresetBaseUrl } from './protocolRules'

interface ModelFormModalProps {
  open: boolean
  editing: LLMConfig | null
  onCancel: () => void
  onSubmit: (values: LLMConfigFormValues) => void
  onTest: () => void
  testing: boolean
  loading: boolean
}

const CHAT_PROTOCOL_OPTIONS = [
  { value: 'openai', label: 'OpenAI 兼容' },
  { value: 'anthropic', label: 'Anthropic' },
]

const PROTOCOL_LABELS: Record<LLMProtocol, string> = {
  openai: 'OpenAI 兼容',
  anthropic: 'Anthropic',
  systemone: 'System One',
}

const PURPOSE_OPTIONS: { value: LlmPurpose; label: string }[] = [
  { value: 'chat', label: '对话/分析（默认对话与知识库清洗/抽取）' },
  { value: 'embedding', label: '向量嵌入（知识库检索）' },
  { value: 'vision', label: '视觉识别（图片理解）' },
  { value: 'decision', label: '结构化判断（盘中执行 L1）' },
]

const PROVIDER_OPTIONS = [
  ...Object.entries(LLM_PROVIDER_PRESETS).map(([value, preset]) => ({
    value,
    label: preset.label,
  })),
  { value: 'custom', label: '自定义' },
]

export function ModelFormModal({
  open,
  editing,
  onCancel,
  onSubmit,
  onTest,
  testing,
  loading,
}: ModelFormModalProps) {
  const [form] = Form.useForm<LLMConfigFormValues>()
  const purpose = Form.useWatch('purpose', form)
  const currentPurpose: LlmPurpose = purpose ?? 'chat'
  const isDecision = currentPurpose === 'decision'
  // 协议由用途派生：decision/embedding 锁定展示，chat/vision 保留人工选择
  const protocolLocked = currentPurpose === 'decision' || currentPurpose === 'embedding'

  useEffect(() => {
    if (open) {
      const capabilities = (editing?.extra?.capabilities ?? {}) as { vision?: boolean }
      if (editing) {
        form.setFieldsValue({
          name: editing.name,
          provider: editing.provider,
          protocol: editing.protocol,
          baseUrl: editing.baseUrl,
          modelName: editing.modelName,
          apiKey: '',
          isDefault: editing.isDefault,
          isActive: editing.isActive,
          purpose: editing.purpose,
          vision: capabilities.vision === true,
        })
      } else {
        form.resetFields()
        form.setFieldsValue({
          provider: 'deepseek',
          protocol: 'openai',
          baseUrl: LLM_PROVIDER_PRESETS.deepseek.baseUrl,
          isActive: true,
          isDefault: false,
          purpose: 'chat',
          vision: false,
        })
      }
    }
  }, [open, editing, form])

  // 端点跟协议走：国内主流厂商双协议端点不同，按「厂商 × 协议」解析默认 Base URL；
  // 自定义供应商不覆盖手填地址
  const linkBaseUrl = (provider: string, protocol: LLMProtocol) => {
    const preset = LLM_PROVIDER_PRESETS[provider]
    if (preset) form.setFieldsValue({ baseUrl: resolvePresetBaseUrl(preset, protocol) })
  }

  const handleProviderChange = (provider: string) => {
    const preset = LLM_PROVIDER_PRESETS[provider]
    if (!preset) return
    const protocol = protocolLocked
      ? protocolForPurpose(currentPurpose, provider, 'openai')
      : chatProtocolForProvider(provider)
    form.setFieldsValue({ protocol })
    linkBaseUrl(provider, protocol)
  }

  const handleProtocolChange = (protocol: LLMProtocol) => {
    linkBaseUrl(form.getFieldValue('provider'), protocol)
  }

  const handlePurposeChange = (value: LlmPurpose) => {
    const provider = form.getFieldValue('provider')
    const prevProtocol = form.getFieldValue('protocol')
    const protocol = protocolForPurpose(value, provider, prevProtocol)
    const updates: Partial<LLMConfigFormValues> = { protocol }
    if (value === 'vision') updates.vision = true // 视觉用途自动开启视觉能力
    form.setFieldsValue(updates)
    if (protocol !== prevProtocol) linkBaseUrl(provider, protocol)
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit(values)
  }

  const protocolOptions = protocolLocked
    ? [
        {
          value: isDecision ? 'systemone' : 'openai',
          label: PROTOCOL_LABELS[isDecision ? 'systemone' : 'openai'],
        },
      ]
    : CHAT_PROTOCOL_OPTIONS

  return (
    <Modal
      title={editing ? '编辑模型配置' : '新增模型配置'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      destroyOnClose
      footer={[
        <Button
          key="test"
          icon={<ExperimentOutlined />}
          onClick={onTest}
          loading={testing}
          disabled={!editing}
          title={editing ? '测试已保存的配置' : '请先保存配置后再测试'}
        >
          测试连接
        </Button>,
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button key="ok" type="primary" onClick={handleOk} loading={loading}>
          确定
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Divider plain orientation="left">
          用途与能力
        </Divider>

        <Form.Item
          label="用途"
          name="purpose"
          rules={[{ required: true, message: '请选择用途' }]}
          extra={
            isDecision
              ? undefined
              : '知识库模型角色槽位按用途过滤候选条目，须与槽位要求一致'
          }
        >
          <Select options={PURPOSE_OPTIONS} onChange={handlePurposeChange} />
        </Form.Item>

        <Form.Item
          label="调用协议"
          name="protocol"
          rules={[{ required: true, message: '请选择协议类型' }]}
          extra={
            isDecision
              ? '由用途决定：判断模型固定走 System One wire 协议'
              : currentPurpose === 'embedding'
                ? '由用途决定：嵌入模型走 OpenAI 兼容协议（嵌入接口为 OpenAI 形状）'
                : '决定实际调用的接口协议，测试连接按所选协议探测'
          }
        >
          <Select options={protocolOptions} disabled={protocolLocked} onChange={handleProtocolChange} />
        </Form.Item>

        {currentPurpose === 'chat' && (
          <Form.Item
            label="设为默认"
            name="isDefault"
            valuePropName="checked"
            extra="未显式指定模型的 AI 调用走该条目（仅对话/分析用途参与默认解析）"
          >
            <Switch />
          </Form.Item>
        )}

        {(currentPurpose === 'chat' || currentPurpose === 'vision') && (
          <Form.Item
            label="视觉能力"
            name="vision"
            valuePropName="checked"
            extra="开启后该模型可用于图片识别（如自选股截图导入），须为支持图片输入的模型"
          >
            <Switch />
          </Form.Item>
        )}

        <Divider plain orientation="left">
          模型接入
        </Divider>

        <Form.Item
          label="名称"
          name="name"
          rules={[{ required: true, message: '请输入名称' }]}
        >
          <Input placeholder="如：DeepSeek V4" />
        </Form.Item>

        <Form.Item
          label="供应商"
          name="provider"
          rules={[{ required: true, message: '请选择供应商' }]}
        >
          <Select options={PROVIDER_OPTIONS} onChange={handleProviderChange} />
        </Form.Item>

        <Form.Item
          label="API 地址 (Base URL)"
          name="baseUrl"
          rules={[{ required: true, message: '请输入 API 地址' }]}
          extra={
            isDecision
              ? '填 API 根地址：OpenRouter https://openrouter.ai/api 或 Codiv https://api.codiv.ai'
              : '选择供应商/协议后自动填充对应端点（可手动修改）；粘贴含 /embeddings、/chat/completions 的完整端点会自动归一'
          }
        >
          <Input placeholder="https://api.deepseek.com" />
        </Form.Item>

        <Form.Item
          label="模型名称"
          name="modelName"
          rules={[{ required: true, message: '请输入模型名称' }]}
          extra={
            isDecision
              ? '固定版本 pin：OpenRouter 填 jev-latest 或 typesafe/jev-1.13；Codiv 填 openjev-0.1；直连 TypeSafe 填 jev-1.13.0'
              : undefined
          }
        >
          <Input placeholder={isDecision ? 'jev-latest' : 'deepseek-chat'} />
        </Form.Item>

        <Form.Item
          label="API Key"
          name="apiKey"
          rules={[{ required: !editing, message: '请输入 API Key' }]}
        >
          <Input.Password placeholder={editing ? '留空表示不修改' : 'sk-...'} />
        </Form.Item>

        <Form.Item label="启用" name="isActive" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}
