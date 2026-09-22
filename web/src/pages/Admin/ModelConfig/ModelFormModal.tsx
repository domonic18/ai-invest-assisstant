import { ExperimentOutlined } from '@ant-design/icons'
import { Button, Form, Input, Modal, Select, Switch } from 'antd'
import { useEffect } from 'react'

import { LLM_PROVIDER_PRESETS } from '@ai-invest/shared'
import type { LLMConfig, LLMConfigFormValues, LlmPurpose } from '@ai-invest/shared'

interface ModelFormModalProps {
  open: boolean
  editing: LLMConfig | null
  onCancel: () => void
  onSubmit: (values: LLMConfigFormValues) => void
  onTest: () => void
  testing: boolean
  loading: boolean
}

const PROTOCOL_OPTIONS = [
  { value: 'openai', label: 'OpenAI 兼容' },
  { value: 'anthropic', label: 'Anthropic' },
]

const PURPOSE_OPTIONS: { value: LlmPurpose; label: string }[] = [
  { value: 'chat', label: '对话/分析（默认对话与知识库清洗/抽取）' },
  { value: 'embedding', label: '向量嵌入（知识库检索）' },
  { value: 'vision', label: '视觉识别（图片理解）' },
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

  const handleProviderChange = (provider: string) => {
    const preset = LLM_PROVIDER_PRESETS[provider]
    if (preset) {
      form.setFieldsValue({ baseUrl: preset.baseUrl, protocol: preset.protocol })
    }
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit(values)
  }

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
          label="协议类型"
          name="protocol"
          rules={[{ required: true, message: '请选择协议类型' }]}
          extra="决定实际调用的接口协议，测试连接按所选协议探测"
        >
          <Select options={PROTOCOL_OPTIONS} />
        </Form.Item>

        <Form.Item
          label="API 地址 (Base URL)"
          name="baseUrl"
          rules={[{ required: true, message: '请输入 API 地址' }]}
          extra="填 API 根地址（如 https://open.bigmodel.cn/api/paas/v4）；粘贴含 /embeddings、/chat/completions 的完整端点会自动归一"
        >
          <Input placeholder="https://api.deepseek.com" />
        </Form.Item>

        <Form.Item
          label="模型名称"
          name="modelName"
          rules={[{ required: true, message: '请输入模型名称' }]}
        >
          <Input placeholder="deepseek-chat" />
        </Form.Item>

        <Form.Item
          label="用途"
          name="purpose"
          rules={[{ required: true, message: '请选择用途' }]}
          extra="知识库模型角色槽位按用途过滤候选条目，须与槽位要求一致"
        >
          <Select options={PURPOSE_OPTIONS} />
        </Form.Item>

        <Form.Item
          label="API Key"
          name="apiKey"
          rules={[{ required: !editing, message: '请输入 API Key' }]}
        >
          <Input.Password placeholder={editing ? '留空表示不修改' : 'sk-...'} />
        </Form.Item>

        <Form.Item label="设为默认" name="isDefault" valuePropName="checked">
          <Switch />
        </Form.Item>

        <Form.Item label="启用" name="isActive" valuePropName="checked">
          <Switch />
        </Form.Item>

        <Form.Item
          label="视觉能力"
          name="vision"
          valuePropName="checked"
          extra="开启后该模型可用于图片识别（如自选股截图导入），须为支持图片输入的模型"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}
